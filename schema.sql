-- 1) USERS
CREATE TABLE users (
    user_id        INT AUTO_INCREMENT PRIMARY KEY,
    name           VARCHAR(50) NOT NULL,
    email          VARCHAR(100),
    created_at     DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 2) TRIPS
CREATE TABLE trips (
    trip_id            INT AUTO_INCREMENT PRIMARY KEY,
    title              VARCHAR(100) NOT NULL,
    start_date         DATE,
    end_date           DATE,
    total_budget_krw   INT,
    created_by         INT,
    CONSTRAINT fk_trips_user
        FOREIGN KEY (created_by) REFERENCES users(user_id)
);

-- 3) TRIP_PARTICIPANTS  (여행-사용자 N:M)
CREATE TABLE trip_participants (
    tp_id      INT AUTO_INCREMENT PRIMARY KEY,
    trip_id    INT NOT NULL,
    user_id    INT NOT NULL,
    role       ENUM('owner', 'member') DEFAULT 'member',
    UNIQUE KEY uk_trip_user (trip_id, user_id),
    CONSTRAINT fk_tp_trip
        FOREIGN KEY (trip_id) REFERENCES trips(trip_id),
    CONSTRAINT fk_tp_user
        FOREIGN KEY (user_id) REFERENCES users(user_id)
);

-- 4) DESTINATIONS (여행의 Day/도시 정보)
CREATE TABLE destinations (
    destination_id   INT AUTO_INCREMENT PRIMARY KEY,
    trip_id          INT NOT NULL,
    day_no           INT NOT NULL,
    country_name     VARCHAR(50),
    city_name        VARCHAR(50),
    note             VARCHAR(255),
    CONSTRAINT fk_dest_trip
        FOREIGN KEY (trip_id) REFERENCES trips(trip_id)
);

-- 5) CURRENCY (통화 & 환율)
CREATE TABLE currency (
    currency_code   VARCHAR(3) PRIMARY KEY,
    currency_name   VARCHAR(20),
    rate_to_krw     DECIMAL(12,4) NOT NULL,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 6) ACTIVITIES (도시 안에서의 일정)
CREATE TABLE activities (
    activity_id      INT AUTO_INCREMENT PRIMARY KEY,
    destination_id   INT NOT NULL,
    name             VARCHAR(100) NOT NULL,
    category         VARCHAR(50),
    start_time       TIME,
    end_time         TIME,
    cost             DECIMAL(12,2),
    currency_code    VARCHAR(3),
    cost_krw         DECIMAL(12,2),
    memo             VARCHAR(255),
    CONSTRAINT fk_act_dest
        FOREIGN KEY (destination_id) REFERENCES destinations(destination_id),
    CONSTRAINT fk_act_currency
        FOREIGN KEY (currency_code) REFERENCES currency(currency_code)
);

-- 7) TRANSPORTS (이동 수단)
CREATE TABLE transports (
    transport_id   INT AUTO_INCREMENT PRIMARY KEY,
    trip_id        INT NOT NULL,
    from_city      VARCHAR(50),
    to_city        VARCHAR(50),
    mode           VARCHAR(30),      -- bus, train, flight 등
    duration_min   INT,
    cost           DECIMAL(12,2),
    currency_code  VARCHAR(3),
    cost_krw       DECIMAL(12,2),
    depart_at      DATETIME,
    CONSTRAINT fk_tran_trip
        FOREIGN KEY (trip_id) REFERENCES trips(trip_id),
    CONSTRAINT fk_tran_currency
        FOREIGN KEY (currency_code) REFERENCES currency(currency_code)
);

-- 8) EXPENSES (지출)
CREATE TABLE expenses (
    expense_id           INT AUTO_INCREMENT PRIMARY KEY,
    trip_id              INT NOT NULL,
    related_activity_id  INT,
    paid_by_user_id      INT NOT NULL,
    amount               DECIMAL(12,2) NOT NULL,
    currency_code        VARCHAR(3) NOT NULL,
    amount_krw           DECIMAL(12,2) NOT NULL,
    category             VARCHAR(50),
    payment_method       VARCHAR(20),
    paid_at              DATETIME,
    memo                 VARCHAR(255),
    CONSTRAINT fk_exp_trip
        FOREIGN KEY (trip_id) REFERENCES trips(trip_id),
    CONSTRAINT fk_exp_act
        FOREIGN KEY (related_activity_id) REFERENCES activities(activity_id),
    CONSTRAINT fk_exp_user
        FOREIGN KEY (paid_by_user_id) REFERENCES users(user_id),
    CONSTRAINT fk_exp_currency
        FOREIGN KEY (currency_code) REFERENCES currency(currency_code)
);

-- 9) EXPENSE_PARTICIPANTS (지출 N빵)
CREATE TABLE expense_participants (
    ep_id             INT AUTO_INCREMENT PRIMARY KEY,
    expense_id        INT NOT NULL,
    user_id           INT NOT NULL,
    share_amount_krw  DECIMAL(12,2) NOT NULL,
    is_settled        BOOLEAN DEFAULT 0,
    settled_at        DATETIME,
    CONSTRAINT fk_ep_exp
        FOREIGN KEY (expense_id) REFERENCES expenses(expense_id),
    CONSTRAINT fk_ep_user
        FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE TABLE settlement_transactions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    trip_id INT NOT NULL,
    payer_name VARCHAR(50) NOT NULL,
    receiver_name VARCHAR(50) NOT NULL,
    amount INT NOT NULL,
    is_done TINYINT(1) DEFAULT 0,
    done_at DATETIME NULL,
    FOREIGN KEY (trip_id) REFERENCES trips(trip_id)
);
