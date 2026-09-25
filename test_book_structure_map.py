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


def test_profiled_sherlock_ignores_toc(tmp_path):
    body=(b"I. A Scandal in Bohemia\nII. The Red-Headed League\n"
          b"I. A SCANDAL IN BOHEMIA\n"+b"a"*900+b"\n"
          b"II. THE RED-HEADED LEAGUE\n"+b"b"*900+b"\n")
    lock=fake_lock(tmp_path,body); lock["source_id"]="1661"
    m=map_exact_structure(lock)
    assert [x["line"] for x in m["navigation"]]==["I. A SCANDAL IN BOHEMIA","II. THE RED-HEADED LEAGUE"]

def test_profiled_moby_drops_toc_epilogue(tmp_path):
    body=(b"EPILOGUE\n"+b"intro "*200+b"\n"
          b"CHAPTER I.\nLOOMINGS\n"+b"a"*900+b"\n"
          b"CHAPTER II.\nTHE CARPET-BAG.\n"+b"b"*900+b"\n"
          b"EPILOGUE.\n"+b"c"*900+b"\n")
    lock=fake_lock(tmp_path,body); lock["source_id"]="15"
    m=map_exact_structure(lock)
    assert m["navigation"][0]["line"]=="CHAPTER I."
    assert m["navigation"][-1]["line"]=="EPILOGUE."

def test_profiled_dorian_starts_second_chapter_one(tmp_path):
    toc=b"".join([f"CHAPTER {r}.\n".encode() for r in ["I","II","III","IV","V"]])
    body=toc+b"THE PREFACE\n"+b"x"*900+b"\nCHAPTER I.\n"+b"a"*900+b"\nCHAPTER II.\n"+b"b"*900+b"\n"
    lock=fake_lock(tmp_path,body); lock["source_id"]="174"
    m=map_exact_structure(lock)
    assert m["navigation"][0]["line"]=="CHAPTER I."
    assert m["navigation"][0]["offset"]>len(toc)
