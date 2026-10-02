"""쇼핑 리스트 (Streamlit 버전)

웹 버전(index.html / app.js)과 같은 PRD 기능을 Streamlit으로 구현한다.
브라우저 localStorage 대신 이 파일 옆의 shopping_list.json에 저장한다.

실행: streamlit run streamlit_app.py
"""

import json
import re
import time
import uuid
from pathlib import Path

import streamlit as st

# 저장 파일 경로
DATA_FILE = Path(__file__).with_name("shopping_list.json")

# 아이템 이름 최대 길이
MAX_NAME_LENGTH = 100

# 마크다운으로 해석될 수 있는 문자 (아이템 이름을 글자 그대로 보여주기 위해 이스케이프)
MARKDOWN_SPECIAL = re.compile(r"([\\`*_{}\[\]()#+\-.!|~<>$:])")


# ---------------------------------------------------------------------------
# 저장 / 불러오기
# ---------------------------------------------------------------------------

def load_items():
    """저장 파일에서 아이템 목록을 불러온다. 깨지거나 잘못된 데이터는 걸러낸다."""
    try:
        parsed = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(parsed, list):
        return []

    items = []
    seen_ids = set()
    for item in parsed:
        if not isinstance(item, dict):
            continue
        item_id, name = item.get("id"), item.get("name")
        if not isinstance(item_id, str) or not isinstance(name, str) or not name.strip():
            continue
        # 중복된 id는 새로 발급한다
        if item_id in seen_ids:
            item_id = uuid.uuid4().hex
        seen_ids.add(item_id)

        created_at = item.get("createdAt")
        items.append({
            "id": item_id,
            "name": name,
            "checked": item.get("checked") is True,
            "createdAt": created_at if isinstance(created_at, (int, float)) else int(time.time() * 1000),
        })
    return items


def save_items(items):
    """아이템 목록을 저장 파일에 쓴다. 쓰는 도중 끊겨도 파일이 깨지지 않도록 임시 파일을 거친다."""
    temp_file = DATA_FILE.with_suffix(".tmp")
    try:
        temp_file.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
        temp_file.replace(DATA_FILE)
    except OSError as error:
        st.toast(f"쇼핑 리스트를 저장하지 못했어요: {error}", icon="⚠️")


def find_item(items, item_id):
    return next((item for item in items if item["id"] == item_id), None)


# ---------------------------------------------------------------------------
# 상태 변경 (위젯 콜백)
# 콜백은 화면을 그리기 전에 실행되므로, 매번 파일에서 읽고 → 바꾸고 → 저장한다.
# ---------------------------------------------------------------------------

def stop_editing():
    st.session_state.editing_id = None


def add_item():
    """입력창의 이름으로 새 아이템을 목록 맨 아래에 추가한다 (빈 값 무시)."""
    name = st.session_state.new_item.strip()
    if not name:
        return

    items = load_items()
    items.append({
        "id": uuid.uuid4().hex,
        "name": name,
        "checked": False,
        "createdAt": int(time.time() * 1000),
    })
    save_items(items)
    stop_editing()


def toggle_item(item_id):
    """체크박스 상태를 아이템에 반영한다."""
    items = load_items()
    item = find_item(items, item_id)
    if item:
        item["checked"] = st.session_state[f"check_{item_id}"]
        save_items(items)


def delete_item(item_id):
    items = [item for item in load_items() if item["id"] != item_id]
    save_items(items)
    if st.session_state.editing_id == item_id:
        stop_editing()


def clear_completed():
    items = [item for item in load_items() if not item["checked"]]
    save_items(items)
    if not find_item(items, st.session_state.editing_id):
        stop_editing()


def start_editing(item_id):
    """수정 모드를 시작한다 (다른 아이템을 수정 중이었다면 그 수정은 취소)."""
    item = find_item(load_items(), item_id)
    if not item:
        return
    st.session_state.editing_id = item_id
    st.session_state[f"edit_{item_id}"] = item["name"]


def save_editing(item_id):
    """수정한 이름을 저장한다. 빈 값이면 원래 이름을 유지한다."""
    name = st.session_state.get(f"edit_{item_id}", "").strip()
    items = load_items()
    item = find_item(items, item_id)
    if item and name:
        item["name"] = name
        save_items(items)
    stop_editing()


# ---------------------------------------------------------------------------
# 화면
# ---------------------------------------------------------------------------

def escape_markdown(text):
    return MARKDOWN_SPECIAL.sub(r"\\\1", text)


def render_item(item):
    item_id = item["id"]

    if item_id == st.session_state.editing_id:
        # 수정 모드: Enter는 첫 번째 제출 버튼(저장)으로 처리된다
        with st.form(key=f"edit_form_{item_id}", border=False):
            with st.container(horizontal=True, vertical_alignment="bottom"):
                st.text_input(
                    f"{item['name']} 이름 수정",
                    key=f"edit_{item_id}",
                    max_chars=MAX_NAME_LENGTH,
                    label_visibility="collapsed",
                )
                st.form_submit_button("저장", type="primary", on_click=save_editing, args=(item_id,))
                st.form_submit_button("취소", on_click=stop_editing)
        return

    # wrap=False: 이름이 길어도 버튼이 다음 줄로 밀리지 않고 이름이 줄바꿈된다
    with st.container(horizontal=True, vertical_alignment="center", wrap=False):
        name = escape_markdown(item["name"])
        # 체크된 아이템: 취소선 + 흐린 색
        label = f":gray[~~{name}~~]" if item["checked"] else name
        st.checkbox(
            label,
            value=item["checked"],
            key=f"check_{item_id}",
            on_change=toggle_item,
            args=(item_id,),
            width="stretch",
            wrap=True,
        )
        st.button("수정", key=f"edit_button_{item_id}", on_click=start_editing, args=(item_id,))
        st.button(
            "삭제",
            key=f"delete_button_{item_id}",
            type="tertiary",
            icon=":material/delete:",
            on_click=delete_item,
            args=(item_id,),
        )


def main():
    st.set_page_config(page_title="쇼핑 리스트", page_icon="🛒", layout="centered")
    st.session_state.setdefault("editing_id", None)

    st.header("🛒 쇼핑 리스트")

    # 아이템 추가: Enter 또는 추가 버튼, 추가 후 입력창 비움
    with st.form("add_form", clear_on_submit=True, border=False):
        with st.container(horizontal=True, vertical_alignment="bottom"):
            st.text_input(
                "추가할 아이템",
                key="new_item",
                placeholder="아이템 입력...",
                max_chars=MAX_NAME_LENGTH,
                label_visibility="collapsed",
            )
            st.form_submit_button("추가", type="primary", on_click=add_item)

    items = load_items()

    if items:
        with st.container(border=True):
            for item in items:
                render_item(item)
    else:
        st.markdown(
            "<div style='text-align:center; padding:2rem 0; color:gray'>"
            "<div style='font-size:2.5rem'>🧺</div>쇼핑 리스트가 비어 있어요</div>",
            unsafe_allow_html=True,
        )

    # 하단 요약: 남은 개수 + 완료 항목 삭제
    total = len(items)
    remaining = sum(not item["checked"] for item in items)
    with st.container(horizontal=True, vertical_alignment="center"):
        st.markdown(f"**{total}**개 중 **{remaining}**개 남음", width="stretch")
        st.button(
            "완료 항목 삭제",
            on_click=clear_completed,
            disabled=total == remaining,
        )


main()
