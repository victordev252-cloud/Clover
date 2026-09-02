import pytest
from utils.core import calculate_equal_parts, calculate_parts, format_duration, parse_timestamp, safe_filename

def test_timestamp_roundtrip_inputs():
    assert parse_timestamp('01:05') == 65
    assert parse_timestamp('01:01:01') == 3661
    assert parse_timestamp('2.5') == 2.5

def test_invalid_timestamp():
    with pytest.raises(ValueError): parse_timestamp('01:70')

def test_parts_never_empty():
    assert calculate_parts(65, 20) == [(0,20),(20,40),(40,60),(60,65)]

def test_equal_parts_cover_duration():
    parts=calculate_equal_parts(120,4)
    assert len(parts)==4 and parts[0][0]==0 and parts[-1][1]==120

def test_safe_filename_blocks_traversal():
    name=safe_filename('../../bad;rm -rf * .mp4')
    assert '/' not in name and '\\' not in name and ';' not in name

def test_format_duration():
    assert format_duration(3661)=='01:01:01'
    assert format_duration(65)=='01:05'
