# Open Gene Literature

유전자명을 입력하면 관련 논문을 찾아 정리하는 **Windows / macOS 데스크톱 앱**입니다.
사람 유전자명을 확인한 뒤 논문 목록, 초록, 유전자 관련 원문 문장, PMID/DOI 링크를 표시합니다.
API 키나 유료 구독은 필요하지 않으며 검색에는 인터넷 연결이 필요합니다.

## 다운로드해서 실행

[최신 릴리스](https://github.com/Newgenes1031/open-gene-literature/releases/latest)에서 운영체제에 맞는 ZIP을 받으세요.

| 운영체제 | 파일 | 실행 방법 |
| --- | --- | --- |
| Windows x64 | `OpenGeneLiterature-windows-x64.zip` | 전체 압축 해제 → 폴더 안의 `OpenGeneLiterature.exe` 실행 |
| Mac Apple Silicon | `OpenGeneLiterature-macos-arm64.zip` | 압축 해제 → `OpenGeneLiterature.app` 실행 |
| Mac Intel | `OpenGeneLiterature-macos-x64.zip` | 압축 해제 → `OpenGeneLiterature.app` 실행 |

실행 파일에는 Python이 포함되어 별도 설치가 필요하지 않습니다.
Windows에서는 EXE 옆의 `_internal` 폴더를 함께 유지하세요.
macOS 배포 파일은 macOS 15 이상을 기준으로 만듭니다. Windows는 64비트 Windows 10/11 환경을 대상으로 합니다.

배포 앱은 Apple Developer ID 공증 및 Windows 발급자 인증서 서명을 하지 않았습니다.
운영체제나 기관 보안 정책이 실행을 제한할 수 있습니다. 다운로드를 신뢰하는 경우에만 OS의 정상 승인 절차를 따르세요.
기관 정책상 실행이 불가능하면 아래 소스 실행 방법을 사용하세요. 앱은 보안 설정 해제를 요구하지 않습니다.

## 사용 방법

1. **유전자명**에 `FASN`, `TP53`, `STAT3`, `p53` 등을 입력합니다.
2. 필요하면 **관심 주제**에 `cancer`, `colorectal cancer` 같은 영어 구문을 입력합니다. 비워도 됩니다.
3. 관련도순·최신순·인용순, 논문 수(1~300)를 선택하고 **검색**을 누릅니다.
4. 목록에서 논문을 고르면 초록과 유전자 관련 문장을 읽을 수 있습니다.
5. **선택 논문 링크 열기**, **보고서 열기**, **CSV 내보내기**로 결과를 사용합니다.

검색 결과는 기본적으로 사용자 문서 폴더의 `OpenGeneLiterature/` 아래에 검색별 폴더로 저장합니다.
창에서 저장 위치를 바꿀 수 있습니다. 각 검색은 `report.html`, `papers.csv`, `report.json`을 만듭니다.

API 응답 캐시는 OS의 사용자 캐시 폴더에 저장합니다. 같은 검색은 캐시 응답을 재사용하며
보고서 JSON에 원래 조회 시각을 기록합니다. 최신 데이터를 다시 받으려면 앱을 닫고 아래 캐시 폴더를 비우세요.

- Windows: `%LOCALAPPDATA%/OpenGeneLiterature`
- macOS: `~/Library/Caches/OpenGeneLiterature`

## Python 소스로 실행

Python 3.10 이상과 Tcl/Tk가 포함된 Python 배포판이 필요합니다. Windows/macOS의 python.org 설치판을 권장합니다.

```sh
python -m pip install .
python gene_literature_gui.py
```

Windows에서 `python`이 없으면 `py -3`를, macOS에서는 `python3`를 사용하세요.
의존성 설치 후 Mac의 `논문검색.command`, Windows의 `Start-Windows.bat`로도 GUI를 열 수 있습니다.

기존 명령줄 기능도 유지합니다.

```sh
python gene_literature.py FASN --context cancer --limit 30 --open
python gene_literature.py TP53 --sort cited --limit 50 --open
python gene_literature.py STAT3 --sort recent --limit 30 --open
```

`--context`는 제목·초록에서 함께 찾을 구문 하나입니다.
`--include-aliases`는 별칭·이전 이름으로 검색을 확장하지만 검색 잡음이 늘 수 있습니다.
사용자가 직접 입력한 별칭은 기본 검색에도 포함합니다. 예: `p53` 입력 시 `TP53`과 `P53`을 검색합니다.
CLI의 캐시·보고서 기본 위치는 소스 폴더 안의 `.cache/`, `reports/`이며 `--cache`, `--output`으로 바꿀 수 있습니다.
`--offline`은 같은 조건으로 이미 받은 응답만 사용합니다.

## 결과 해석

- 공식 유전자명·별칭 확인: HGNC. **사람 유전자만 지원**합니다.
- 문헌 검색: Europe PMC의 PubMed 색인 레코드. 결과 논문의 실험 종·조직·질환은 혼합될 수 있습니다.
- 인용 수: Europe PMC 기준이며 Web of Science 인용 수와 다릅니다.
- 논문 분류: PubMed publication type에 따른 리뷰·임상시험·철회 관련·기타 구분입니다.
- 유전자 관련 문장: 초록 원문 발췌입니다. AI 요약이 아니며, 인과관계를 입증하는 자동 판정도 아닙니다.
- 철회 표지는 제공된 publication type에 의존합니다. 초록이 없으면 내용을 만들어 넣지 않습니다.
- 여러 유전자로 해석되는 별칭은 자동 선택하지 않고 공식 이름을 요구합니다.
- 일반 단어와 겹치는 유전자명은 오탐이 생길 수 있습니다. 개별 논문을 확인하세요.
- 기본 30건, 최대 300건을 수집합니다. 전체 문헌을 빠짐없이 수집하는 기능은 아닙니다.

이번 버전에는 한국어/LLM 요약, 문장 단위 인과관계 추출, upstream regulator 추론, pathway 분석,
Web of Science 연동이 포함되어 있지 않습니다.

## 개발·검증·빌드

```sh
python -m unittest discover -s tests -v
python tests/gui_smoke.py
python -m pip install -r requirements-build.txt
python tools/build_desktop.py
```

GUI 통합 검증은 실제 Tcl/Tk 창을 생성하므로 데스크톱 환경이 필요합니다.
빌드 스크립트는 현재 OS용 앱을 만들고, **패키징된 앱의 Tcl/Tk 시작과 HTTPS 인증서 포함 여부**를 확인한 뒤 ZIP으로 묶습니다.
Windows 앱은 Windows에서, Mac 앱은 Mac에서 각각 빌드합니다.

GitHub Actions는 `main` 변경 시 Windows x64·Mac Apple Silicon·Mac Intel에서 테스트와 빌드를 실행합니다.
세 빌드가 모두 성공하면 `pyproject.toml`의 버전으로 GitHub Release를 게시합니다.
이미 존재하는 버전은 덮어쓰지 않으므로 다음 배포 시 코드와 `pyproject.toml` 버전을 함께 올리세요.

## 라이선스·출처

직접 작성한 코드는 [MIT](LICENSE) 라이선스입니다. 논문 초록·보고서·캐시는 배포 파일에서 제외합니다.
논문 콘텐츠의 재배포는 논문별 조건을 따릅니다. [타사 고지](THIRD_PARTY_NOTICES.md)를 참고하세요.

IPA Gene View의 공개 설명을 참고한 독립 구현입니다. IPA 설치본·계정이 없어 IPA 앱을 역공학하지 않았습니다.
REA는 개발 조사용으로 검토했으며 배포 앱에는 포함하지 않습니다. [조사 메모](docs/research.md)에 범위를 기록했습니다.

- [HGNC REST API](https://www.genenames.org/help/rest/)
- [Europe PMC REST API](https://europepmc.org/RestfulWebService)
- [IPA Gene Search 공개 튜토리얼](https://qiagen.my.salesforce-sites.com/KnowledgeBase/KnowledgeNavigatorPage?categoryName=IPA&id=kA41i000000L69HCAS)
- [REA 공식 저장소](https://github.com/morluto/rea)
