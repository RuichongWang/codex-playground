# -*- coding: utf-8 -*-
u"""命令行。`--chain-head` 每次都要传:写入之前你必须先看过账的头。"""
import argparse
import json
import sys

from done import card as C
from done import judge as J
from done import ledger as L

LEDGER = u".done/ledger.jsonl"


def _eye(pairs):
    u"""--eye a3=pass:alex:照 README 跑通 → {a3: {pass, by, note}}"""
    out = {}
    for p in pairs or ():
        cid, _, rest = p.partition(u"=")
        verdict, by, note = (rest.split(u":", 2) + [u"", u""])[:3]
        out[cid.strip()] = {u"pass": verdict.strip() == u"pass", u"by": by.strip(),
                            u"note": note.strip()}
    return out


def _print(row):
    b = row[u"body"]
    print(u"%s #%d %s" % (row[u"kind"], row[u"seq"], b.get(u"card", u"")))
    for ln in b.get(u"lines", ()):
        print(u"  %-4s %-5s %s   evidence: %s"
              % (ln[u"id"], ln[u"档"], u"pass" if ln[u"passed"] else u"FAIL",
                 json.dumps(ln[u"evidence"], ensure_ascii=False)))
    if u"passed" in b:
        print(u"→ %s" % (u"PASSED" if b[u"passed"] else u"NOT DONE"))
    print(u"新的链头:%s" % row[u"hash"])


def main(argv=None):
    ap = argparse.ArgumentParser(prog=u"done")
    ap.add_argument(u"--ledger", default=LEDGER)
    sub = ap.add_subparsers(dest=u"cmd")
    for name in (u"open", u"amend", u"judge"):
        s = sub.add_parser(name)
        s.add_argument(u"cardfile")
        s.add_argument(u"--chain-head", required=True)
        s.add_argument(u"--by", default=u"")
        if name == u"amend":
            s.add_argument(u"--why", required=True)
        if name == u"judge":
            s.add_argument(u"--at", default=u"HEAD")
            s.add_argument(u"--repo", default=u".")
            s.add_argument(u"--eye", action=u"append")
    sub.add_parser(u"head")
    sub.add_parser(u"verify")
    sub.add_parser(u"log")
    a = ap.parse_args(argv)
    try:
        if a.cmd == u"head":
            print(L.head(a.ledger))
        elif a.cmd == u"verify":
            ok, why = L.verify(a.ledger)
            print(u"账完好" if ok else u"账断了:%s" % why)
            return 0 if ok else 1
        elif a.cmd == u"log":
            for r in L.read(a.ledger):
                print(u"#%d %-7s %s" % (r[u"seq"], r[u"kind"],
                                        json.dumps(r[u"body"], ensure_ascii=False)[:160]))
        elif a.cmd == u"open":
            _print(C.open_card(a.ledger, a.cardfile, a.by, a.chain_head))
        elif a.cmd == u"amend":
            _print(C.amend(a.ledger, a.cardfile, a.why, a.by, a.chain_head))
        elif a.cmd == u"judge":
            _print(J.judge(a.ledger, a.cardfile, a.repo, a.at, a.chain_head, _eye(a.eye)))
        else:
            ap.print_help()
        return 0
    except L.Refused as e:
        sys.stderr.write(u"拒绝 %s\n" % e)
        return 2


if __name__ == u"__main__":
    sys.exit(main())
