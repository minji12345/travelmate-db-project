# TravelMate – 여행 일정 및 정산 관리 시스템

## 1. 프로젝트 개요
여행 일정(Day/도시/액티비티)과 공동 지출을 관리하고,
참여자 간 정산을 데이터베이스 기반으로 처리하는 웹 애플리케이션입니다.

Flask는 입력/출력만 담당하며,
정산 계산과 데이터 관리는 MySQL(DBMS) 중심으로 설계되었습니다.

## 2. 실행 환경
- Python 3.x
- Flask
- MySQL 8.x

## 3. 실행 방법
1. MySQL에서 schema.sql 실행
2. (선택) sample_data.sql 실행
3. app.py에서 DB 접속 정보 수정
4. 아래 명령어 실행

```bash
python app.py
