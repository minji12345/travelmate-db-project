-- 기본 유저
INSERT INTO users (name, email)
VALUES
    ('민지', 'minji@example.com'),
    ('예지', 'yeji@example.com'),
    ('지훈', 'jihoon@example.com');

-- 통화 & 환율 
INSERT INTO currency (currency_code, currency_name, rate_to_krw)
VALUES
    ('KRW', 'Korean Won', 1),
    ('JPY', 'Japanese Yen', 9.42),
    ('USD', 'US Dollar', 1468),
    ('EUR', 'Euro', 1711),
    ('CNY', 'Chinese Yuan', 208),
    ('HKD', 'Hong Kong Dollar', 189),
    ('TWD', 'New Taiwan Dollar', 47.1),
    ('THB', 'Thai Baht', 38),
    ('VND', 'Vietnam Dong', 0.055),
    ('SGD', 'Singapore Dollar', 1130);


-- 여행 1개 (규슈 3박4일)
INSERT INTO trips (title, start_date, end_date, total_budget_krw, created_by)
VALUES
    ('규슈 3박4일 여행', '2025-02-01', '2025-02-04', 800000, 1);

-- 참여자 (민지=owner, 예지=member)
INSERT INTO trip_participants (trip_id, user_id, role)
VALUES
    (1, 1, 'owner'),
    (1, 2, 'member'),
    (1, 3, 'member');

-- Day/도시
INSERT INTO destinations (trip_id, day_no, country_name, city_name, note)
VALUES
    (1, 1, 'Japan', 'Fukuoka', '후쿠오카 시내 구경'),
    (1, 2, 'Japan', 'Kumamoto', '구마모토/아소'),
    (1, 3, 'Japan', 'Nagasaki', '나가사키 관광');

-- 액티비티 (간단 예시)
INSERT INTO activities
(destination_id, name, category, start_time, end_time, cost, currency_code, cost_krw, memo)
VALUES
    (1, '텐진 쇼핑', 'shopping', '10:00', '12:00', 3000, 'JPY', 27300, '잡화 쇼핑'),
    (2, '아소산 투어', 'tour',    '09:00', '15:00', 8000, 'JPY', 72800, '버스 투어'),
    (3, '글로버 가든', 'sightseeing', '14:00', '16:00', 2000, 'JPY', 18200, '입장료');

-- 이동 수단
INSERT INTO transports
(trip_id, from_city, to_city, mode, duration_min, cost, currency_code, cost_krw, depart_at)
VALUES
    (1, 'Busan', 'Fukuoka', 'ferry', 180, 120000, 'KRW', 120000, '2025-02-01 08:00:00'),
    (1, 'Fukuoka', 'Kumamoto', 'train', 70, 4500, 'JPY', 40950, '2025-02-02 09:00:00'),
    (1, 'Kumamoto', 'Nagasaki', 'train', 90, 5000, 'JPY', 45500, '2025-02-03 10:00:00');

-- 지출 (민지가 결제한 항목들)
INSERT INTO expenses
(trip_id, related_activity_id, paid_by_user_id, amount, currency_code, amount_krw,
 category, payment_method, paid_at, memo)
VALUES
    (1, 1, 1, 3000, 'JPY', 27300, 'shopping', 'card', '2025-02-01 11:30:00', '텐진 쇼핑'),
    (1, 2, 1, 8000, 'JPY', 72800, 'tour', 'card', '2025-02-02 15:30:00', '아소 투어'),
    (1, 3, 2, 2000, 'JPY', 18200, 'sightseeing', 'cash', '2025-02-03 15:00:00', '글로버 가든');

-- 지출 참여자 (N빵 결과 : 3명이 균등 부담)
-- 총원 3명 기준, share_amount_krw 값은 대략적으로 입력
INSERT INTO expense_participants
(expense_id, user_id, share_amount_krw, is_settled)
VALUES
    (1, 1, 9100, 0),
    (1, 2, 9100, 0),
    (1, 3, 9100, 0),

    (2, 1, 24266, 0),
    (2, 2, 24266, 0),
    (2, 3, 24266, 0),

    (3, 1, 6066, 0),
    (3, 2, 6066, 0),
    (3, 3, 6066, 0);
