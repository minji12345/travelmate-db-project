from flask import Flask, render_template, request, redirect, url_for
import pymysql

app = Flask(__name__)

# --------------------------
# DB 연결 함수
# --------------------------
def get_connection():
    return pymysql.connect(
        host='localhost',
        user='root',
        password='password', 
        db='travelmate',
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )

# --------------------------
# 라우트
# --------------------------

@app.route('/')
def index():
    # 메인 페이지 -> 여행 목록으로 리다이렉트
    return redirect(url_for('trip_list'))


# 여행 목록
@app.route('/trips')
def trip_list():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT trip_id, title, start_date, end_date
                FROM trips
                ORDER BY start_date;
            """)
            trips = cur.fetchall()
    finally:
        conn.close()

    return render_template('trip_list.html', trips=trips)


# 새 여행 생성 (GET: 폼 / POST: 저장)
@app.route('/trips/new', methods=['GET', 'POST'])
def trip_form():
    if request.method == 'POST':
        title = request.form.get('title')
        start_date = request.form.get('start_date') or None
        end_date = request.form.get('end_date') or None

        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO trips (title, start_date, end_date)
                    VALUES (%s, %s, %s)
                """, (title, start_date, end_date))
            conn.commit()
        finally:
            conn.close()

        return redirect(url_for('trip_list'))

    # GET일 때는 폼만 보여줌
    return render_template('trip_form.html')

@app.route('/trips/<int:trip_id>')
def trip_detail(trip_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:

            # 1) 기본 여행 정보
            cur.execute("""
                SELECT trip_id, title, start_date, end_date, total_budget_krw
                FROM trips
                WHERE trip_id = %s
            """, (trip_id,))
            trip = cur.fetchone()

            # 2) Day / 도시 목록
            cur.execute("""
                SELECT destination_id, day_no, country_name, city_name, note
                FROM destinations
                WHERE trip_id = %s
                ORDER BY day_no;
            """, (trip_id,))
            destinations = cur.fetchall()

            # 3) 액티비티 목록
            cur.execute("""
                SELECT a.activity_id, d.day_no, d.city_name,
                       a.name, a.category, a.cost_krw, a.memo
                FROM activities a
                JOIN destinations d ON a.destination_id = d.destination_id
                WHERE d.trip_id = %s
                ORDER BY d.day_no, a.start_time;
            """, (trip_id,))
            activities = cur.fetchall()

            # 4) 지출 내역
            cur.execute("""
                SELECT e.expense_id,
                       u.name AS payer_name,
                       e.category,
                       e.amount,
                       e.currency_code,
                       e.amount_krw,
                       e.paid_at,
                       e.memo
                FROM expenses e
                JOIN users u ON e.paid_by_user_id = u.user_id
                WHERE e.trip_id = %s
                ORDER BY e.paid_at;
            """, (trip_id,))
            expenses = cur.fetchall()
            
            # 4-1) 여행 참가자 목록
            cur.execute("""
                SELECT u.user_id, u.name
                FROM trip_participants tp
                JOIN users u ON tp.user_id = u.user_id
                WHERE tp.trip_id = %s
                ORDER BY u.user_id;
            """, (trip_id,))
            participants = cur.fetchall()

            # 5) "원래" 정산 결과 (지출/참가자 기준)
            cur.execute("""
                SELECT
                    u.user_id,
                    u.name,
                    IFNULL(paid.total_paid, 0)   AS total_paid,
                    IFNULL(shared.total_share, 0) AS total_share,
                    IFNULL(paid.total_paid, 0) - IFNULL(shared.total_share, 0) AS balance
                FROM trip_participants tp
                JOIN users u ON tp.user_id = u.user_id
                LEFT JOIN (
                    SELECT paid_by_user_id AS user_id,
                           SUM(amount_krw) AS total_paid
                    FROM expenses
                    WHERE trip_id = %s
                    GROUP BY paid_by_user_id
                ) paid ON u.user_id = paid.user_id
                LEFT JOIN (
                    SELECT ep.user_id,
                           SUM(ep.share_amount_krw) AS total_share
                    FROM expense_participants ep
                    JOIN expenses e ON ep.expense_id = e.expense_id
                    WHERE e.trip_id = %s
                    GROUP BY ep.user_id
                ) shared ON u.user_id = shared.user_id
                WHERE tp.trip_id = %s
                ORDER BY u.user_id;
            """, (trip_id, trip_id, trip_id))
            settlement_rows = cur.fetchall()

            # 6) 이미 완료된 송금 내역(누가 누구에게 얼마 보냈는지)
            cur.execute("""
                SELECT payer_name, receiver_name, amount
                FROM settlement_transactions
                WHERE trip_id = %s AND is_done = 1
            """, (trip_id,))
            settled_rows = cur.fetchall()

        # --- 여기부터는 파이썬에서 계산 ---

        # 6-1) 사람별 '보낸 금액' / '받은 금액' 합산
        paid_map = {}      # 이름 -> 보낸 총 금액
        received_map = {}  # 이름 -> 받은 총 금액

        for r in settled_rows:
            amt = float(r["amount"])
            payer = r["payer_name"]
            receiver = r["receiver_name"]

            paid_map[payer] = paid_map.get(payer, 0) + amt
            received_map[receiver] = received_map.get(receiver, 0) + amt

        # 6-2) 송금까지 반영한 "현재 balance"와 "현재 총 결제액" 계산
        #   - original_balance = total_paid - total_share
        #   - new_balance = original_balance + 보낸금액 - 받은금액
        #   - final_paid  = total_share + new_balance
        settlement = []
        for row in settlement_rows:
            name = row["name"]
            original_balance = float(row["balance"])
            total_share = float(row["total_share"])

            paid_total = paid_map.get(name, 0)
            received_total = received_map.get(name, 0)

            new_balance = original_balance + paid_total - received_total

            # 화면 보기 좋은 값으로 반올림 (원 단위)
            new_balance_rounded = round(new_balance)
            final_paid = round(total_share + new_balance)   # 송금까지 포함해 최종적으로 부담한 금액

            new_row = dict(row)
            new_row["balance"] = new_balance_rounded
            new_row["final_paid"] = final_paid
            settlement.append(new_row)

        # 7) 남은 balance 기준으로 송금 정리(transactions) 계산
        receivers = []  # 아직 돈을 더 받아야 하는 사람 (balance > 0)
        payers = []     # 아직 돈을 더 내야 하는 사람 (balance < 0)

        for row in settlement:
            if row["balance"] > 0:
                receivers.append({"name": row["name"], "amount": row["balance"]})
            elif row["balance"] < 0:
                payers.append({"name": row["name"], "amount": -row["balance"]})

        transactions = []
        i, j = 0, 0

        while i < len(payers) and j < len(receivers):
            pay = payers[i]
            rec = receivers[j]

            send_amount = min(pay["amount"], rec["amount"])

            # 금액도 int 로 깔끔하게
            send_amount = int(round(send_amount))

            transactions.append({
                "from": pay["name"],
                "to": rec["name"],
                "amount": send_amount
            })

            pay["amount"] -= send_amount
            rec["amount"] -= send_amount

            if pay["amount"] <= 0:
                i += 1
            if rec["amount"] <= 0:
                j += 1

    finally:
        conn.close()

    return render_template(
        "trip_detail.html",
        trip=trip,
        destinations=destinations,
        activities=activities,
        expenses=expenses,
        settlement=settlement,     # 송금까지 반영된 현재 정산 결과
        transactions=transactions,  # 아직 남은 송금 리스트
        participants=participants
    )


# 지출 추가 (새 지출 입력 + 참가자 N빵)
@app.route('/trips/<int:trip_id>/expenses/new', methods=['GET', 'POST'])
def expense_form(trip_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # 여행 정보
            cur.execute("""
                SELECT trip_id, title, start_date, end_date
                FROM trips
                WHERE trip_id = %s
            """, (trip_id,))
            trip = cur.fetchone()

            # 이 여행 참가자 목록
            cur.execute("""
                SELECT u.user_id, u.name
                FROM trip_participants tp
                JOIN users u ON tp.user_id = u.user_id
                WHERE tp.trip_id = %s
                ORDER BY u.user_id;
            """, (trip_id,))
            participants = cur.fetchall()

        # POST: 저장 처리
        if request.method == 'POST':
            payer_id = int(request.form.get('payer_id'))
            amount = float(request.form.get('amount'))                  # 사용자가 입력한 금액
            currency_code = request.form.get('currency_code')           # 선택한 통화
            category = request.form.get('category') or None
            payment_method = request.form.get('payment_method') or None
            memo = request.form.get('memo') or None

            # 1) 통화 환율 가져오기 (currency 테이블에서)
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT rate_to_krw
                    FROM currency
                    WHERE currency_code = %s
                """, (currency_code,))
                row = cur.fetchone()

            if not row:
                # 해당 통화가 currency 테이블에 없으면 에러
                raise ValueError(f"currency 테이블에 {currency_code} 환율이 없습니다.")

            rate = float(row['rate_to_krw'])

            # 2) KRW로 자동 환산
            amount_krw = amount * rate

            with conn.cursor() as cur:
                # 3) expenses INSERT
                cur.execute("""
                    INSERT INTO expenses
                        (trip_id, paid_by_user_id, amount, currency_code,
                         amount_krw, category, payment_method, paid_at, memo)
                    VALUES
                        (%s, %s, %s, %s, %s, %s, %s, NOW(), %s)
                """, (
                    trip_id,
                    payer_id,
                    amount,
                    currency_code,
                    amount_krw,
                    category,
                    payment_method,
                    memo
                ))
                expense_id = cur.lastrowid

                # 4) N빵 처리 (expense_participants)
                if participants:
                    share = round(amount_krw / len(participants), 2)
                    for p in participants:
                        cur.execute("""
                            INSERT INTO expense_participants
                                (expense_id, user_id, share_amount_krw)
                            VALUES (%s, %s, %s)
                        """, (expense_id, p['user_id'], share))

            conn.commit()
            return redirect(url_for('trip_detail', trip_id=trip_id))

    finally:
        conn.close()

    # GET 요청일 때는 폼 화면만 보여줌
    return render_template(
        'expense_form.html',
        trip=trip,
        participants=participants
    )

# 지출 수정
@app.route('/expenses/<int:expense_id>/edit', methods=['GET', 'POST'])
def expense_edit(expense_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # 수정할 지출 1건
            cur.execute("""
                SELECT
                    e.expense_id,
                    e.trip_id,
                    e.paid_by_user_id,
                    e.amount,
                    e.currency_code,
                    e.category,
                    e.payment_method,
                    e.memo,
                    t.title,
                    t.start_date,
                    t.end_date
                FROM expenses e
                JOIN trips t ON e.trip_id = t.trip_id
                WHERE e.expense_id = %s
            """, (expense_id,))
            expense = cur.fetchone()

            if not expense:
                # 없는 지출이면 목록으로
                return redirect(url_for('trip_list'))

            trip_id = expense['trip_id']

            # 이 여행 참가자 (N빵 기준)
            cur.execute("""
                SELECT u.user_id, u.name
                FROM trip_participants tp
                JOIN users u ON tp.user_id = u.user_id
                WHERE tp.trip_id = %s
                ORDER BY u.user_id;
            """, (trip_id,))
            participants = cur.fetchall()

        # POST: 수정 저장
        if request.method == 'POST':
            payer_id = int(request.form.get('payer_id'))
            amount = float(request.form.get('amount'))
            currency_code = request.form.get('currency_code')
            category = request.form.get('category') or None
            payment_method = request.form.get('payment_method') or None
            memo = request.form.get('memo') or None

            with conn.cursor() as cur:
                # 환율 조회
                cur.execute("""
                    SELECT rate_to_krw
                    FROM currency
                    WHERE currency_code = %s
                """, (currency_code,))
                row = cur.fetchone()

            if not row:
                raise ValueError(f"currency 테이블에 {currency_code} 환율이 없습니다.")

            rate = float(row['rate_to_krw'])
            amount_krw = amount * rate

            with conn.cursor() as cur:
                # expenses 수정
                cur.execute("""
                    UPDATE expenses
                    SET paid_by_user_id = %s,
                        amount = %s,
                        currency_code = %s,
                        amount_krw = %s,
                        category = %s,
                        payment_method = %s,
                        memo = %s
                    WHERE expense_id = %s
                """, (
                    payer_id,
                    amount,
                    currency_code,
                    amount_krw,
                    category,
                    payment_method,
                    memo,
                    expense_id
                ))

                # 기존 N빵 내역 삭제 후 다시 계산
                cur.execute("""
                    DELETE FROM expense_participants
                    WHERE expense_id = %s
                """, (expense_id,))

                if participants:
                    share = round(amount_krw / len(participants), 2)
                    for p in participants:
                        cur.execute("""
                            INSERT INTO expense_participants
                                (expense_id, user_id, share_amount_krw)
                            VALUES (%s, %s, %s)
                        """, (expense_id, p['user_id'], share))

            conn.commit()
            return redirect(url_for('trip_detail', trip_id=trip_id))

    finally:
        conn.close()

    # GET: 수정 폼
    return render_template(
        'expense_edit.html',
        trip=expense,          # trip 정보 + expense에 같이 있음
        expense=expense,
        participants=participants
    )

# 지출 삭제
@app.route('/expenses/<int:expense_id>/delete', methods=['POST'])
def expense_delete(expense_id):
    conn = get_connection()
    trip_id = None
    try:
        with conn.cursor() as cur:
            # 먼저 어느 여행에 속한 지출인지 확인
            cur.execute("""
                SELECT trip_id
                FROM expenses
                WHERE expense_id = %s
            """, (expense_id,))
            row = cur.fetchone()

            if not row:
                return redirect(url_for('trip_list'))

            trip_id = row['trip_id']

            # N빵 내역 삭제
            cur.execute("""
                DELETE FROM expense_participants
                WHERE expense_id = %s
            """, (expense_id,))

            # 지출 행 삭제
            cur.execute("""
                DELETE FROM expenses
                WHERE expense_id = %s
            """, (expense_id,))

        conn.commit()
    finally:
        conn.close()

    return redirect(url_for('trip_detail', trip_id=trip_id))


# Day/도시 추가
@app.route('/trips/<int:trip_id>/destinations/new', methods=['GET', 'POST'])
def destination_form(trip_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # 여행 정보
            cur.execute("""
                SELECT trip_id, title, start_date, end_date
                FROM trips
                WHERE trip_id = %s
            """, (trip_id,))
            trip = cur.fetchone()

        if request.method == 'POST':
            day_no = int(request.form.get('day_no'))
            country_name = request.form.get('country_name') or None
            city_name = request.form.get('city_name') or None
            note = request.form.get('note') or None

            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO destinations
                    (trip_id, day_no, country_name, city_name, note)
                    VALUES (%s, %s, %s, %s, %s)
                """, (trip_id, day_no, country_name, city_name, note))
            conn.commit()
            return redirect(url_for('trip_detail', trip_id=trip_id))

    finally:
        conn.close()

    return render_template('destination_form.html', trip=trip)

@app.route('/destinations/<int:destination_id>/edit', methods=['GET', 'POST'])
def destination_edit(destination_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # 1) 기존 데이터 불러오기
            cur.execute("""
                SELECT destination_id, trip_id, day_no, country_name, city_name, note
                FROM destinations
                WHERE destination_id = %s
            """, (destination_id,))
            dest = cur.fetchone()

        # 만약 없는 destination_id라면 그냥 여행 목록으로 보내기 (안전장치)
        if not dest:
            return redirect(url_for('trip_list'))

        # 2) 폼 제출(POST)이면 DB 업데이트
        if request.method == 'POST':
            day_no = request.form.get('day_no')
            country_name = request.form.get('country_name')
            city_name = request.form.get('city_name')
            note = request.form.get('note')

            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE destinations
                    SET day_no = %s,
                        country_name = %s,
                        city_name = %s,
                        note = %s
                    WHERE destination_id = %s
                """, (day_no, country_name, city_name, note, destination_id))
            conn.commit()

            # 수정한 뒤, 원래 여행 상세 페이지로 돌아가기
            return redirect(url_for('trip_detail', trip_id=dest['trip_id']))

    finally:
        conn.close()

    # 3) GET 요청이면 수정 폼 보여주기
    return render_template('destination_edit.html', dest=dest)

@app.route('/destinations/<int:destination_id>/delete', methods=['POST'])
def destination_delete(destination_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # 리다이렉트를 위해 trip_id 먼저 가져오기
            cur.execute("""
                SELECT trip_id
                FROM destinations
                WHERE destination_id = %s
            """, (destination_id,))
            row = cur.fetchone()
            trip_id = row['trip_id'] if row else None

            # 1) 이 Day에 속한 액티비티 삭제
            cur.execute("""
                DELETE FROM activities
                WHERE destination_id = %s
            """, (destination_id,))

            # 2) Day(도시) 삭제
            cur.execute("""
                DELETE FROM destinations
                WHERE destination_id = %s
            """, (destination_id,))
        conn.commit()
    finally:
        conn.close()

    if trip_id:
        return redirect(url_for('trip_detail', trip_id=trip_id))
    else:
        return redirect(url_for('trip_list'))

# 액티비티 추가 (통화 선택 + KRW 자동 환산 적용)
@app.route('/trips/<int:trip_id>/activities/new', methods=['GET', 'POST'])
def activity_form(trip_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # 여행 정보
            cur.execute("""
                SELECT trip_id, title, start_date, end_date
                FROM trips
                WHERE trip_id = %s
            """, (trip_id,))
            trip = cur.fetchone()

            # Day/도시 목록
            cur.execute("""
                SELECT destination_id, day_no, country_name, city_name
                FROM destinations
                WHERE trip_id = %s
                ORDER BY day_no;
            """, (trip_id,))
            destinations = cur.fetchall()

        if request.method == 'POST':
            destination_id = int(request.form.get('destination_id'))
            name = request.form.get('name')
            category = request.form.get('category') or None
            start_time = request.form.get('start_time') or None
            end_time = request.form.get('end_time') or None
            amount = request.form.get('amount')
            currency_code = request.form.get('currency_code')
            memo = request.form.get('memo') or None

            # 금액 입력이 아예 없으면 비용 없이 저장
            if not amount:
                cost = None
                currency_code = None
                cost_krw = None
            else:
                amount = float(amount)

                if currency_code:
                    # 환율 조회
                    with conn.cursor() as cur:
                        cur.execute("""
                            SELECT rate_to_krw
                            FROM currency
                            WHERE currency_code = %s
                        """, (currency_code,))
                        row = cur.fetchone()

                    if not row:
                        raise ValueError(f"currency 테이블에 {currency_code} 환율이 없습니다.")

                    rate = float(row['rate_to_krw'])
                    cost_krw = amount * rate
                    cost = amount
                else:
                    # 통화 없이 금액만 입력 → 원화로 간주
                    currency_code = 'KRW'
                    cost = amount
                    cost_krw = amount

            # INSERT
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO activities
                        (destination_id, name, category, start_time, end_time,
                         cost, currency_code, cost_krw, memo)
                    VALUES
                        (%s, %s, %s, %s, %s,
                         %s, %s, %s, %s)
                """, (
                    destination_id, name, category, start_time, end_time,
                    cost, currency_code, cost_krw, memo
                ))

            conn.commit()
            return redirect(url_for('trip_detail', trip_id=trip_id))

    finally:
        conn.close()

    return render_template(
        'activity_form.html',
        trip=trip,
        destinations=destinations
    )

@app.route('/activities/<int:activity_id>/edit', methods=['GET', 'POST'])
def activity_edit(activity_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # 1) 현재 액티비티 + 해당 여행 정보 조회
            cur.execute("""
                SELECT 
                    a.activity_id,
                    a.destination_id,
                    a.name,
                    a.category,
                    a.start_time,
                    a.end_time,
                    a.cost,
                    a.currency_code,
                    a.cost_krw,
                    a.memo,
                    d.trip_id
                FROM activities a
                JOIN destinations d ON a.destination_id = d.destination_id
                WHERE a.activity_id = %s
            """, (activity_id,))
            activity = cur.fetchone()

        # 잘못된 id면 여행 목록으로
        if not activity:
            return redirect(url_for('trip_list'))

        trip_id = activity['trip_id']

        # 같은 여행에 속한 Day/도시 목록 (드롭다운용)
        with conn.cursor() as cur:
            cur.execute("""
                SELECT destination_id, day_no, country_name, city_name
                FROM destinations
                WHERE trip_id = %s
                ORDER BY day_no;
            """, (trip_id,))
            destinations = cur.fetchall()

        # ----- POST: 수정 저장 -----
        if request.method == 'POST':
            destination_id = int(request.form.get('destination_id'))
            name = request.form.get('name')
            category = request.form.get('category') or None
            start_time = request.form.get('start_time') or None
            end_time = request.form.get('end_time') or None
            amount = request.form.get('amount')
            currency_code = request.form.get('currency_code') or None
            memo = request.form.get('memo') or None

            # 금액/통화 처리 (새로 입력한 값 기준으로 다시 환율 계산)
            if not amount:
                cost = None
                currency_code = None
                cost_krw = None
            else:
                amount = float(amount)

                if currency_code:
                    with conn.cursor() as cur:
                        cur.execute("""
                            SELECT rate_to_krw
                            FROM currency
                            WHERE currency_code = %s
                        """, (currency_code,))
                        row = cur.fetchone()

                    if not row:
                        raise ValueError(f"currency 테이블에 {currency_code} 환율이 없습니다.")

                    rate = float(row['rate_to_krw'])
                    cost = amount
                    cost_krw = amount * rate
                else:
                    # 통화 선택 안 하면 KRW로 처리
                    currency_code = 'KRW'
                    cost = amount
                    cost_krw = amount

            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE activities
                    SET destination_id = %s,
                        name = %s,
                        category = %s,
                        start_time = %s,
                        end_time = %s,
                        cost = %s,
                        currency_code = %s,
                        cost_krw = %s,
                        memo = %s
                    WHERE activity_id = %s
                """, (
                    destination_id, name, category, start_time, end_time,
                    cost, currency_code, cost_krw, memo, activity_id
                ))
            conn.commit()

            return redirect(url_for('trip_detail', trip_id=trip_id))

    finally:
        conn.close()

    # GET: 수정 폼 표시
    return render_template(
        'activity_edit.html',
        activity=activity,
        destinations=destinations
    )

# 액티비티 삭제
@app.route('/activities/<int:activity_id>/delete', methods=['POST'])
def activity_delete(activity_id):
    conn = get_connection()
    trip_id = None
    try:
        with conn.cursor() as cur:
            # 이 액티비티가 어느 여행(trip)에 속하는지 찾기
            cur.execute("""
                SELECT d.trip_id
                FROM activities a
                JOIN destinations d ON a.destination_id = d.destination_id
                WHERE a.activity_id = %s
            """, (activity_id,))
            row = cur.fetchone()

            if not row:
                return redirect(url_for('trip_list'))

            trip_id = row['trip_id']

            # 액티비티 삭제
            cur.execute("""
                DELETE FROM activities
                WHERE activity_id = %s
            """, (activity_id,))

        conn.commit()
    finally:
        conn.close()

    return redirect(url_for('trip_detail', trip_id=trip_id))

# 여행 참여 인원 추가
@app.route('/trips/<int:trip_id>/participants/add', methods=['POST'])
def add_participant(trip_id):
    name = request.form.get('name')

    # 이름이 비어 있으면 그냥 다시 상세 페이지로
    if not name or not name.strip():
        return redirect(url_for('trip_detail', trip_id=trip_id))

    name = name.strip()

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # 1) 같은 이름의 user가 이미 있으면 재사용, 없으면 새로 생성
            cur.execute("""
                SELECT user_id
                FROM users
                WHERE name = %s
            """, (name,))
            row = cur.fetchone()

            if row:
                user_id = row['user_id']
            else:
                cur.execute("""
                    INSERT INTO users (name)
                    VALUES (%s)
                """, (name,))
                user_id = cur.lastrowid

            # 2) 이 여행(trip)에 참가자로 등록 (중복 방지용 INSERT IGNORE)
            cur.execute("""
                INSERT IGNORE INTO trip_participants (trip_id, user_id)
                VALUES (%s, %s)
            """, (trip_id, user_id))

        conn.commit()
    finally:
        conn.close()

    return redirect(url_for('trip_detail', trip_id=trip_id))

@app.route('/trips/<int:trip_id>/delete', methods=['POST'])
def trip_delete(trip_id):
    """여행 1개 전체 삭제 (연관된 데이터까지 정리)"""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # 1) 지출 참여자( N빵 내역 ) 삭제
            cur.execute("""
                DELETE ep FROM expense_participants ep
                JOIN expenses e ON ep.expense_id = e.expense_id
                WHERE e.trip_id = %s
            """, (trip_id,))

            # 2) 정산 송금 내역 삭제
            cur.execute("""
                DELETE FROM settlement_transactions
                WHERE trip_id = %s
            """, (trip_id,))

            # 3) 지출 내역 삭제
            cur.execute("""
                DELETE FROM expenses
                WHERE trip_id = %s
            """, (trip_id,))

            # 4) 액티비티 삭제
            cur.execute("""
                DELETE a FROM activities a
                JOIN destinations d ON a.destination_id = d.destination_id
                WHERE d.trip_id = %s
            """, (trip_id,))

            # 5) Day / 도시 삭제
            cur.execute("""
                DELETE FROM destinations
                WHERE trip_id = %s
            """, (trip_id,))

            # 6) 여행 참가자 정보 삭제
            cur.execute("""
                DELETE FROM trip_participants
                WHERE trip_id = %s
            """, (trip_id,))

            # 7) 마지막으로 trips 삭제
            cur.execute("""
                DELETE FROM trips
                WHERE trip_id = %s
            """, (trip_id,))

        conn.commit()
    finally:
        conn.close()

    return redirect(url_for('trip_list'))

@app.route('/trips/<int:trip_id>/participants/<int:user_id>/delete', methods=['POST'])
def participant_delete(trip_id, user_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # 1) 이 사용자가 N빵에 포함된 기록 삭제
            cur.execute("""
                DELETE ep
                FROM expense_participants ep
                JOIN expenses e ON ep.expense_id = e.expense_id
                WHERE e.trip_id = %s
                  AND ep.user_id = %s
            """, (trip_id, user_id))

            # 2) 이 사용자가 결제자로 들어간 지출 삭제
            cur.execute("""
                DELETE FROM expenses
                WHERE trip_id = %s
                  AND paid_by_user_id = %s
            """, (trip_id, user_id))

            # 3) 참가자 목록에서 제거
            cur.execute("""
                DELETE FROM trip_participants
                WHERE trip_id = %s
                  AND user_id = %s
            """, (trip_id, user_id))
        conn.commit()
    finally:
        conn.close()

    # 다시 해당 여행 상세로 돌아가기
    return redirect(url_for('trip_detail', trip_id=trip_id))

@app.route('/trips/<int:trip_id>/settlement/done', methods=['POST'])
def settlement_done(trip_id):
    payer = request.form.get('payer')
    receiver = request.form.get('receiver')
    amount = request.form.get('amount')

    try:
        amount_value = int(float(amount))
    except (TypeError, ValueError):
        amount_value = 0

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO settlement_transactions
                (trip_id, payer_name, receiver_name, amount, is_done, done_at)
                VALUES (%s, %s, %s, %s, 1, NOW())
            """, (trip_id, payer, receiver, amount_value))
        conn.commit()
    finally:
        conn.close()

    return redirect(url_for('trip_detail', trip_id=trip_id))


if __name__ == '__main__':
    # debug=True 는 개발용이라 과제 시연 때는 있어도 괜찮음
    app.run(debug=True)
