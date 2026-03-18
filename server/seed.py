from server.core.domain.model.query import Query

SEED_QUERIES = [
    Query(
        id=None,
        title="활성 사용자 조회",
        description="현재 활성 상태인 사용자 목록을 최신순으로 조회합니다.",
        purpose="조회",
        tags="user,active",
        sql_text="SELECT * FROM users WHERE is_active = true ORDER BY created_at DESC;",
    ),
    Query(
        id=None,
        title="주문 금액 집계",
        description="일별 주문 금액 합계를 집계합니다.",
        purpose="집계",
        tags="order,payment",
        sql_text="SELECT DATE(order_date) AS dt, SUM(amount) AS total FROM orders GROUP BY DATE(order_date) ORDER BY dt DESC;",
    ),
    Query(
        id=None,
        title="탈퇴 사용자 삭제",
        description="90일 이상 경과한 탈퇴 사용자 데이터를 삭제합니다.",
        purpose="삭제",
        tags="user,cleanup",
        sql_text="DELETE FROM users WHERE status = 'withdrawn' AND updated_at < NOW() - INTERVAL '90 days';",
    ),
    Query(
        id=None,
        title="상품 가격 수정",
        description="전자제품 카테고리의 오래된 상품 가격을 10% 인상합니다.",
        purpose="수정",
        tags="product,price",
        sql_text="UPDATE products SET price = price * 1.1 WHERE category = 'electronics' AND updated_at < '2024-01-01';",
    ),
    Query(
        id=None,
        title="월별 매출 리포트",
        description="월별 판매 건수와 매출액을 집계하는 리포트 쿼리입니다.",
        purpose="집계",
        tags="sales,report",
        sql_text="SELECT TO_CHAR(sale_date, 'YYYY-MM') AS month, COUNT(*) AS cnt, SUM(total) AS revenue FROM sales GROUP BY TO_CHAR(sale_date, 'YYYY-MM') ORDER BY month DESC;",
    ),
]
