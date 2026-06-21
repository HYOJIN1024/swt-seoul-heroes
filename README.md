# Snowflake Korea Internal Awards 2026 🏆

Snowflake World Tour Seoul 행사용 내부 시상식 앱

## 기능
- 👗 AI 베스트 드레서 — Cortex AI 패션 채점
- 🦶 맨발에 땀나 상 — 만보기 스크린샷 자동 인식
- 🖥️ 전광판 디스플레이 모드 (실시간 리더보드)
- 🔐 관리자 페이지 (점수 수정 / 삭제)

## 파일 구조
```
├── korea_awards_app.py   # 메인 앱
├── environment.yml       # 패키지 의존성
└── README.md
```

## 관리자 비밀번호
`ADMIN_PASSWORD` 변수 (앱 코드 상단) — 배포 전 반드시 변경하세요.

## 패키지
- snowflake-ml-python (Cortex AI)
- pillow (이미지 처리)
