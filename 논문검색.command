#!/bin/zsh
cd -- "${0:A:h}" || exit 1
python3 gene_literature_gui.py
if [ $? -ne 0 ]; then
  printf '\n실행에 실패했습니다. README의 소스 실행 방법을 확인하세요. Enter를 누르면 종료합니다. '
  read -r finish_prompt
fi
