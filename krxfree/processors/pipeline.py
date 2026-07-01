#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Knowledge 생성 파이프라인 — 순서 고정: Timeline -> KnowledgeMerge -> InvestmentCase.

새 Processor 추가 시 이 PIPELINE 리스트에 이름만 추가하면 된다(registry 에 @register 만
해두면 개별 배선 코드 수정 불필요). Phase2-2(Summary/Context/Importance), Phase2-3(Wiki/Alias/
RelatedCompany) 도 같은 방식으로 여기에 이름만 추가해 확장할 예정.
"""
# 아래 import 는 registry 등록(@register) 부작용을 위한 것 — 직접 호출은 registry.get() 으로.
from . import timeline_processor, knowledge_merge_processor, investment_case_processor  # noqa: F401
from . import registry

PIPELINE = ["knowledge_merge", "investment_case"]   # "timeline" 은 events 인자가 달라 별도 호출


def run(code, events):
    """code 종목의 Knowledge 를 이번 실행에서 확인된 events 로 증분 업데이트.
    실패해도 예외를 그대로 던진다 — 호출부(screener.py)가 try/except 로 감싸
    Knowledge 문제가 브리핑 생성 자체를 막지 않도록 한다."""
    registry.get("timeline")(code, events)
    result = None
    for name in PIPELINE:
        result = registry.get(name)(code)
    return result
