# 📁 Versioned File Manager – Backend & Behavior Spec (MVP)

> 범용 생산성 파일을 위한 로컬 버전 관리 애플리케이션  
> macOS / Python 기반 / 로컬 우선 설계

---

## 1. 앱 목표 (Purpose)

- 파일 포맷과 무관한 **버전 관리**
- “헷갈리지 않게, 언제든 되돌릴 수 있게”
- 실제 파일 이름은 건드리지 않고, **표시 이름(Display Name)** 중심 관리
- Git / Silverstack / Hedge 개념을 **일반 사용자용 UX로 단순화**

---

## 2. 핵심 사용자 흐름

### 2.1 파일 등록 & 버전 생성
1. 파일 선택 → 등록
2. **커밋 입력 필수**
3. 등록 취소 시 → **완전 롤백**
4. 버전 번호: `v1, v2, v3 …`

### 2.2 파일 열기
- 더블클릭 → OS 기본 앱
- 옵션:
  - 특정 앱으로 열기
  - “이 앱으로 항상 열기”(macOS 관성 유지)

### 2.3 수정 감지
- Smart Verify:
  - `size + mtime` 빠른 비교
  - 변경 시 → `xxHash64` 검증
- 옵션:
  - 항상 해시 검증(느림)
- 상태:
  - `OK / MODIFIED / MISSING / UNKNOWN`

### 2.4 새 버전 생성
- 수정 감지 시:
  - “파일이 수정되었습니다. 새 버전을 만드시겠습니까?”
- 기본 저장 방식:
  - `Light(pointer)`
- 커밋 코멘트 필수 (버전당 1개)

---

## 3. 버전(Version) 규칙

- 버전당 **Commit 코멘트 1개**
- 댓글/스레드 ❌
- 커밋은 **제목형 요약**
  - 예: `타이틀 수정`, `최종본`

### 표시 정보(최소)
- v번호
- 커밋 메시지
- 시간

### Pin
- 텍스트 표시 ❌
- **버전 클릭 시 핀 아이콘만 표시**

---

## 4. Restore 규칙

- Restore는 **버전 번호 증가 없음**
- 새 파일 생성
- 파일명 규칙:

```
{original_filename}__v{N}_{RestoreLabel}.{ext}
```

- RestoreLabel:
  - 로컬라이즈
  - 예: `복원 파일`, `Restore File`

- 히스토리 기록:
  - Commit ❌
  - Event로만 기록

---

## 5. Display Name (표시 이름)

- 실제 파일명 변경 ❌
- UI용 이름
- 편집 방법:
  - 리스트 인라인 편집
    - macOS: Enter
    - Windows: F2
    - 우클릭 메뉴
  - Info 패널에서도 편집 가능

### Rename 로그
- 기본 OFF
- 옵션으로 ON 가능
- ON 시 이벤트 기록:

```
YYYY-MM-DD HH:MM:SS 표시 이름이 변경되었습니다 (A → B)
```

---

## 6. Events (파일별 타임라인)

### 기록 대상
- Restore
- Pin / Unpin
- Delete (Archive / Remove / Trash)
- Job 실패/취소
- Verify: `MODIFIED / MISSING`만

### 기록 제외
- Verify OK
- 내부 자동 작업

### UI
- **파일별 타임라인에만 표시**
- Commit은 타임라인이 아님 (버전 카드에만 표시)
- 정렬:
  - 최신순 / 오래된순 (옵션)

---

## 7. Delete 정책

삭제 시 항상 선택 다이얼로그 표시:

1. **아카이브**
   - 앱 목록에서 숨김
2. **앱에서 제거**
   - 메타데이터/버전 기록 삭제
   - 실제 파일 유지
3. **휴지통으로 이동**
   - 실제 파일 삭제

- 기본값 저장 가능

---

## 8. Tags

- 정규화 구조:
  - `tags`
  - `tag_links`
- 저장 규칙:
  - DB: 소문자 단어만 (`final`)
  - UI: `#final`
- 적용 대상:
  - File (기본)
  - Version (고급)

---

## 9. Search (FTS5)

### 검색 범위
- 표시 이름
- 경로 일부
- 파일 노트
- **모든 커밋 메시지**
- 태그

### UX
- 실시간 필터
- 검색어 없음:
  - 즐겨찾기 ⭐
  - 최근 커밋 파일
- 결과:
  - 파일 단위만 표시
- 선택된 파일만:
  - 인라인 매칭 문장 1줄 표시

---

## 10. Favorites & Recents

- 즐겨찾기:
  - 단순 ⭐ 토글
- Recents:
  - `last_committed_at` 기준

---

## 11. Job Queue

- 복수 작업 대기열
- 실행:
  - 기본 1개
  - 설정으로 동시 실행 수 변경 가능
- 작업 유형:
  - Hash verify
  - Pin copy
  - Restore
  - Relink scan
- 기능:
  - 진행률
  - 취소
  - 일시정지/재개
- UI:
  - **팝업 창**
  - Always-on-top 옵션

---

## 12. Relink

### 지원 방식
- 수동 Relink (파일 선택)
- 자동 Relink:
  - 루트 폴더 1개 선택
  - 파일명/확장자 → size/mtime → hash 순 매칭
  - **후보 제시 + 사용자 확인**

### 후처리
- Relink 후 즉시 검증 실행
- 결과가 MODIFIED면 경고 + 재선택

---

## 13. Storage

- 저장소 루트:
  - `settings.storage_root_path`
- Pin(copy) 저장소 접근 불가 시:
  - **읽기 전용 모드**
  - 경고 표시

---

## 14. Open With

- macOS 방식 유지
- 우선순위:
  1. 파일별 지정 앱
  2. 확장자 기본 앱
  3. OS 기본
- “이 앱으로 항상 열기” 지원

---

## 15. Metadata 수집

### 공통(모든 파일)
- size
- mtime
- extension
- xxHash64

### 파일 타입별
- 이미지: EXIF
- 영상: 기본 미디어 메타데이터
- 문서: 추후 확장

---

## 16. 기본 UI 레이아웃

- Finder 스타일
  - 사이드바: Projects / Recents / Favorites
  - 메인 리스트
  - 우측 Inspector (상세/버전/이벤트)

---

## 상태 요약

- 백엔드 엔티티/ERD 확정
- 핵심 UX 규칙 확정
- Relink / Search / Version / Event 정책 종료
- 다음 단계: **디자인**
