from book_structure_map import map_exact_structure

def fake_lock(tmp_path,data:bytes):
    p=tmp_path/"book.txt"; p.write_bytes(data)
    import hashlib
    return {"source_file":str(p),"canonical_sha256":hashlib.sha256(data).hexdigest()}

def test_offsets_reassemble_exactly(tmp_path):
    data=(b"CONTENTS\nCHAPTER I\nCHAPTER II\n\n"
          b"CHAPTER I\nFirst chapter prose " + b"x"*900 + b"\n"
          b"CHAPTER II\nSecond chapter prose " + b"y"*900 + b"\n")
    m=map_exact_structure(fake_lock(tmp_path,data))
    rebuilt=b"".join(data[s["start"]:s["end"]] for s in m["segments"])
    assert rebuilt==data
    assert m["exact_reassembly_verified"] is True
    assert m["text_modified"] is False

def test_whitespace_is_not_normalized(tmp_path):
    data=b"CHAPTER I\r\nA  line\twith spaces.\r\n"+b"z"*900+b"\r\n"
    m=map_exact_structure(fake_lock(tmp_path,data))
    rebuilt=b"".join(data[s["start"]:s["end"]] for s in m["segments"])
    assert rebuilt==data
