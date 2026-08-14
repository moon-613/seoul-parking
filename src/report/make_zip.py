"""제출용 소스코드 zip 생성 -> submission/seoul-parking.zip

왜 필요한가
----------
macOS 에서 만든 zip 은 한글 파일명에 **UTF-8 플래그(0x800)가 붙지 않는 경우**가 있다.
그러면 Windows 기본 압축 풀기에서 `03_최종데이터/` 가 `03_∞╡£∞óàδì░∞¥┤φä░` 로 깨진다.
심사자가 어느 OS 를 쓸지 모르니 플래그를 확실히 붙여야 한다.

파이썬 `zipfile` 은 파일명에 비ASCII 가 있으면 UTF-8 로 인코딩하고 플래그를 자동으로
세운다. 그래서 `zip` 명령 대신 이 스크립트를 쓴다. 만든 뒤에는 실제로 플래그가
붙었는지, `.env` 가 섞이지 않았는지 **직접 열어서 검사**한다.

무엇을 담나
----------
`git ls-files` 가 알려주는 **추적 파일의 현재 작업본**을 담는다.
`git archive` 를 쓰지 않는 이유는 그쪽이 마지막 커밋 시점 내용을 담기 때문이다.
문서를 고치고 아직 커밋하지 않았다면 그 수정이 빠진다.

`.env` · `.venv` · `__pycache__` 는 애초에 추적 대상이 아니라 자동으로 빠지고,
내부 문서(멘토링 브리핑)는 EXCLUDE 에 적어 뺀다.

압축을 풀면 파일이 흩어지지 않도록 `seoul-parking/` 폴더 하나로 감싼다.

실행
----
  python -m src.report.make_zip
  python -m src.report.make_zip --out /경로/파일.zip
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import zipfile

from src.utils.logger import get_logger
from src.utils.settings import ROOT_DIR

logger = get_logger(__name__)

OUT_PATH = ROOT_DIR / "submission" / "seoul-parking.zip"
TOP_DIR = "seoul-parking"

# 저장소에는 있지만 제출본에는 넣지 않을 것 (내부용 문서)
EXCLUDE = {"멘토링_브리핑.xlsx"}

# 이런 게 들어가면 사고다 — 만든 뒤 검사한다
FORBIDDEN = (".env", ".venv/", "__pycache__/", ".DS_Store")


def tracked_files() -> list[str]:
    """git 이 추적 중인 파일 목록. -z 로 받아 한글 경로가 따옴표로 이스케이프되는 걸 피한다."""
    out = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT_DIR, capture_output=True, check=True,
    ).stdout.decode("utf-8")
    return [p for p in out.split("\0") if p]


def build(out_path) -> list[str]:
    paths = [p for p in tracked_files() if p not in EXCLUDE]
    missing = [p for p in paths if not (ROOT_DIR / p).exists()]
    if missing:
        logger.error(f"추적 목록에는 있으나 파일이 없습니다: {missing}")
        raise SystemExit(1)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        for p in paths:
            z.write(ROOT_DIR / p, arcname=f"{TOP_DIR}/{p}")
    return paths


def verify(out_path) -> int:
    """만든 zip 을 다시 열어 인코딩·금지항목·개수를 확인한다."""
    fail = 0
    with zipfile.ZipFile(out_path) as z:
        infos = z.infolist()
        bad = z.testzip()
        if bad:
            logger.error(f"  [손상  ] {bad}")
            fail += 1

        # ① 한글 파일명에 UTF-8 플래그가 붙었는가
        nonascii = [i for i in infos if any(ord(c) > 127 for c in i.filename)]
        noflag = [i.filename for i in nonascii if not i.flag_bits & 0x800]
        if noflag:
            logger.error(f"  [인코딩] UTF-8 플래그 없음 {len(noflag)}개 — Windows 에서 깨집니다")
            fail += 1
        else:
            logger.info(f"  [인코딩] 한글 파일명 {len(nonascii)}개 전부 UTF-8 플래그 정상")

        # ② 들어가면 안 되는 것
        for pat in FORBIDDEN:
            hit = [i.filename for i in infos
                   if pat in i.filename and not i.filename.endswith(".env.example")]
            if hit:
                logger.error(f"  [금지  ] '{pat}' 포함: {hit[:3]}")
                fail += 1
        if not fail:
            logger.info("  [금지  ] .env · .venv · __pycache__ 없음")

        # ③ 압축을 풀면 폴더 하나로 나오는가
        roots = {i.filename.split("/")[0] for i in infos}
        if roots != {TOP_DIR}:
            logger.error(f"  [구조  ] 최상위가 여럿입니다: {sorted(roots)}")
            fail += 1
        else:
            logger.info(f"  [구조  ] 최상위 폴더 하나 — {TOP_DIR}/")

        raw = sum(i.file_size for i in infos)
        logger.info(f"  [규모  ] {len(infos)}개 파일 · 압축 {out_path.stat().st_size/1e6:.1f}MB "
                    f"(원본 {raw/1e6:.1f}MB)")
    return fail


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(OUT_PATH), help="생성 경로")
    args = ap.parse_args()

    from pathlib import Path
    out_path = Path(args.out)

    paths = build(out_path)
    logger.info(f"생성 — {out_path.relative_to(ROOT_DIR) if out_path.is_relative_to(ROOT_DIR) else out_path}"
                f" ({len(paths)}개 파일)")
    logger.info("검사")
    if verify(out_path):
        logger.error("제출하면 안 되는 상태입니다.")
        sys.exit(1)
    logger.info("제출 가능합니다.")


if __name__ == "__main__":
    main()
