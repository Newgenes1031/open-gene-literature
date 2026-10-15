# 조사 메모 · 2026-10-15

## 이번 범위

사용자가 선택한 첫 기능: 유전자명 → 관련 레퍼런스 논문 정리.
사용자 확인: morluto/rea가 맞으며 현재 IPA 설치본이나 사용할 화면은 없음. 공개 자료와 데이터로 먼저 구현.

## 공개 정보로 확인한 점

IPA의 Gene Search 튜토리얼은 Gene View에서 유전자 정보, 경로, literature findings,
최근 추가된 findings, supporting abstracts/papers 링크를 볼 수 있다고 설명한다.
이것은 공개 기능 명세이며, IPA 내부 구현·데이터 스키마를 관찰한 결과가 아니다.

- https://qiagen.my.salesforce-sites.com/KnowledgeBase/KnowledgeNavigatorPage?categoryName=IPA&id=kA41i000000L69HCAS
- https://qiagen.my.salesforce-sites.com/KnowledgeBase?id=kA41i000000L5sBCAS

IPA의 upstream regulator 분석은 QIAGEN Knowledge Base의 부호가 있는 조절 관계를 사용한다.
논문 서지 목록에서 바로 복원되는 데이터가 아니다. 후속 버전에서는 CollecTRI/OmniPath와 Reactome을
검토할 수 있다. CollecTRI는 주로 TF–표적 관계이며 IPA의 약물·사이토카인 등 모든 조절인자 범위와 같지 않다.
라이선스는 원 데이터별로 다르므로 코드의 오픈소스 여부와 별도로 다뤄야 한다.

- https://pmc.ncbi.nlm.nih.gov/articles/PMC3928520/
- https://decoupler.scverse.org/en/latest/api/generated/decoupler.op.collectri.html
- https://reactome.org/download-data

Web of Science Starter는 API 키와 사용 플랜이 필요하며 기본 서지/인용 정보를 제공한다.
Expanded는 별도 유료 라이선스가 필요하다. 이 MVP는 키 없이 Europe PMC의 PubMed 색인 레코드로 검색한다.

- https://developer.clarivate.com/apis/wos-starter
- https://developer.clarivate.com/apis/wos

## REA 상태와 역할

공식 npm 패키지 `rea-agents` 6.5.0을 이 프로젝트의 `tools/rea/`에만 설치했다.
설치 시 lifecycle script는 실행하지 않았다. CLI 버전·도움말 실행을 확인했다.
Node.js 24.19.0에서 CLI 실행을 확인했다.

```sh
node tools/rea/node_modules/rea-agents/scripts/rea.mjs --help
```

REA CLI는 앱 바이너리·JavaScript/Electron·브라우저 관찰을 지원한다.
이 MVP에서는 IPA 대상이 없으므로 REA를 통한 IPA 관찰, 디컴파일, 내부 API 분석은 수행하지 않았다.
유전자 논문 검색 코드는 공개 API 문서로 독립 작성했으며 REA 산출물에서 복원한 코드가 아니다.
향후 IPA 화면이나 앱이 제공되면 검색 입력·결과·문헌 링크 동작을 관찰하고 증거와 한계를 기록할 수 있다.

- https://github.com/morluto/rea
- https://raw.githubusercontent.com/morluto/rea/main/docs/browser-observation.md
