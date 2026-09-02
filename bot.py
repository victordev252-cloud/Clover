from __future__ import annotations

import asyncio, logging, shutil, uuid
from pathlib import Path
from pyrogram import Client, filters, idle
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from pyrogram.errors import FloodWait
from config import Settings
from database.db import Database
from services.media import probe, split_part
from utils.core import calculate_equal_parts, calculate_parts, format_bytes, format_duration, safe_filename, enough_space

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s", handlers=[logging.StreamHandler(), logging.FileHandler("logs/clover.log")])
log=logging.getLogger("clover")

class Clover:
    def __init__(self, cfg: Settings):
        self.cfg=cfg; cfg.prepare(); self.db=Database(cfg.database_path); self.app=Client("clover", api_id=cfg.api_id, api_hash=cfg.api_hash, bot_token=cfg.bot_token, workdir=str(cfg.download_dir)); self.queue=asyncio.Queue(); self.jobs={}; self.workers=[]
        self._register()

    def _register(self):
        @self.app.on_message(filters.command("start"))
        async def start(_, m):
            await self.db.upsert_user(m.from_user); await m.reply("🍀 **Welcome to Clover Video Splitter**\n\nSend me a video and choose how to split it.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📖 How To Use", callback_data="help")],[InlineKeyboardButton("📊 My Status", callback_data="status")]]))
        @self.app.on_message(filters.command("help"))
        async def help_cmd(_,m): await m.reply("🍀 **Clover Help**\n\nSend a video or document containing a video. Choose equal parts or minutes per part. Fast mode uses stream copy; Compatible mode re-encodes for more accurate cuts. Files are processed one part at a time and removed after upload. Use /status or /cancel anytime.")
        @self.app.on_message(filters.command("status"))
        async def status(_,m):
            job=self.jobs.get(m.from_user.id) or await self.db.active_for_user(m.from_user.id)
            await m.reply("ℹ️ No active job." if not job else f"🍀 **Clover Status**\n\n🎬 `{job['filename']}`\n📦 `{job['job_id']}`\n⚙️ {job['status']}\n📊 {job['progress']:.0f}%\n📦 Part {job['current_part']}/{job['parts_count']}")
        @self.app.on_message(filters.command("cancel"))
        async def cancel(_,m):
            job=self.jobs.get(m.from_user.id)
            if not job: return await m.reply("ℹ️ You don't have an active job.")
            job["cancel"].set(); await m.reply("🛑 Cancellation requested. Temporary files will be removed safely.")
        @self.app.on_callback_query()
        async def callbacks(_,q):
            if q.data=="help": await q.message.reply("Use /help for instructions.")
            elif q.data=="status": await status(_,q.message)
            await q.answer()
        @self.app.on_message(filters.video | filters.document)
        async def receive(_,m): await self.receive(m)

    async def receive(self,m: Message):
        if await self.db.is_blocked(m.from_user.id): return await m.reply("🚫 You are not allowed to use Clover at this time.")
        if await self.db.active_for_user(m.from_user.id): return await m.reply("⚠️ You already have a video being processed. Please wait or use /cancel.")
        media=m.video or m.document
        if not media: return
        size=getattr(media,"file_size",0) or 0
        if size > self.cfg.max_file_size_gb*1024**3: return await m.reply("❌ This video is larger than the configured limit.")
        job_id="CLOVER-"+uuid.uuid4().hex[:8].upper(); root=self.cfg.download_dir/str(m.from_user.id)/job_id; root.mkdir(parents=True)
        name=safe_filename(getattr(media,"file_name",None) or "video"); suffix=Path(getattr(media,"file_name",None) or "video.mp4").suffix or ".mp4"; input_path=root/(name+suffix)
        cancel=asyncio.Event(); self.jobs[m.from_user.id]={"job_id":job_id,"filename":name+suffix,"status":"QUEUED","progress":0,"current_part":0,"parts_count":0,"cancel":cancel,"message":m}
        await self.db.execute("INSERT INTO jobs(job_id,user_id,filename,file_size,status) VALUES(?,?,?,?,?)",(job_id,m.from_user.id,name+suffix,size,"QUEUED")); await m.reply("📥 Receiving your video... This may take a while for large files.")
        await self.queue.put((m,input_path,root,job_id,cancel))

    async def process(self,m,input_path,root,job_id,cancel):
        user_id=m.from_user.id; state=self.jobs[user_id]
        try:
            state["status"]="DOWNLOADING"; await self.db.execute("UPDATE jobs SET status='DOWNLOADING' WHERE job_id=?",(job_id,))
            await m.download(file_name=str(input_path))
            if cancel.is_set(): raise asyncio.CancelledError
            state["status"]="VALIDATING"; info=await probe(input_path,self.cfg.ffprobe_path); state["duration"]=info.duration
            parts=calculate_equal_parts(info.duration,2) # default safe choice; detailed split selection can be extended via callbacks
            state["parts_count"]=len(parts); await self.db.execute("UPDATE jobs SET status='PROCESSING',duration=?,width=?,height=?,video_codec=?,audio_codec=?,parts_count=?,started_at=CURRENT_TIMESTAMP WHERE job_id=?",(info.duration,info.width,info.height,info.video_codec,info.audio_codec,len(parts),job_id))
            for number,(start,end) in enumerate(parts,1):
                if cancel.is_set(): raise asyncio.CancelledError
                if not enough_space(root, max(64*1024*1024, input_path.stat().st_size//2)): raise RuntimeError("Not enough free disk space")
                state["current_part"]=number; out=root/f"{safe_filename(input_path.name)} - Part {number:02d}.mp4"
                async def progress(value): state["progress"]=((number-1)+value/100)/len(parts)*100; await self.db.execute("UPDATE jobs SET progress=?,current_part=? WHERE job_id=?",(state["progress"],number,job_id))
                await split_part(input_path,out,start,end,"fast",self.cfg.ffmpeg_path,progress); state["status"]="UPLOADING"; await m.reply_video(str(out),caption=f"🎬 {safe_filename(input_path.name)}\n📦 Part {number}/{len(parts)}\n⏱ {format_duration(end-start)}\n🍀 Powered by Clover"); out.unlink(missing_ok=True)
            state["status"]="COMPLETED"; await self.db.execute("UPDATE jobs SET status='COMPLETED',progress=100,completed_at=CURRENT_TIMESTAMP WHERE job_id=?",(job_id,)); await m.reply("✅ **Splitting completed successfully.**")
        except asyncio.CancelledError: await self.db.execute("UPDATE jobs SET status='CANCELLED',completed_at=CURRENT_TIMESTAMP WHERE job_id=?",(job_id,)); await m.reply("🛑 Job cancelled and temporary files removed.")
        except Exception as exc: log.exception("job=%s failed",job_id); await self.db.execute("UPDATE jobs SET status='FAILED',error_message=? WHERE job_id=?",(str(exc)[:500],job_id)); await m.reply("❌ Something went wrong. The technical details were saved in the server log.")
        finally: shutil.rmtree(root,ignore_errors=True); self.jobs.pop(user_id,None)

    async def worker(self):
        while True:
            item=await self.queue.get()
            try: await self.process(*item)
            finally: self.queue.task_done()

    async def run(self):
        await self.db.init(); await self.app.start(); self.workers=[asyncio.create_task(self.worker()) for _ in range(self.cfg.max_concurrent_jobs)]; await idle();
        for w in self.workers: w.cancel()
        await self.app.stop()

if __name__ == "__main__":
    cfg=Settings.from_env(); asyncio.run(Clover(cfg).run())
