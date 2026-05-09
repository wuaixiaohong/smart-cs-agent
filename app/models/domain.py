from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    session_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    intent: Mapped[str | None] = mapped_column(String(128), nullable=True)
    needs_human: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    order_no: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(64), default="default_user")
    product_name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="已下单")
    courier: Mapped[str | None] = mapped_column(String(64), nullable=True)
    waybill: Mapped[str | None] = mapped_column(String(64), nullable=True)
    amount: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class Coupon(Base):
    __tablename__ = "coupons"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    description: Mapped[str] = mapped_column(String(256), nullable=False)
    threshold: Mapped[float] = mapped_column(Float, nullable=False)
    discount: Mapped[float] = mapped_column(Float, nullable=False)
    expire_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Product(Base):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    stock: Mapped[int] = mapped_column(Integer, default=0)
    rating: Mapped[float] = mapped_column(Float, default=5.0)
    category: Mapped[str] = mapped_column(String(64), default="通用")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class FAQ(Base):
    __tablename__ = "faqs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    question: Mapped[str] = mapped_column(String(512), nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(64), default="通用")
    priority: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    session_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    user_input: Mapped[str] = mapped_column(Text, nullable=False)
    reply: Mapped[str] = mapped_column(Text, nullable=False)
    intent: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_safe: Mapped[bool] = mapped_column(Boolean, default=True)
    audit_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    needs_human: Mapped[bool] = mapped_column(Boolean, default=False)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


async def seed_data(session) -> None:
    """初始化种子数据"""
    from sqlalchemy import select, func as sqlfunc

    # 订单
    result = await session.execute(select(sqlfunc.count(Order.id)))
    if result.scalar() == 0:
        orders = [
            Order(order_no="ORD20240509-001", product_name="智能手机 X1", status="已发货", courier="顺丰快递", waybill="SF1234567890", amount=2999.0),
            Order(order_no="ORD20240501-002", product_name="无线降噪耳机 Pro", status="已签收", courier="圆通快递", waybill="YT9876543210", amount=599.0),
            Order(order_no="ORD20240420-003", product_name="轻薄笔记本 Air", status="已完成", courier="中通快递", waybill="ZT5555555555", amount=5999.0),
            Order(order_no="ORD20240508-004", product_name="智能手表 S3", status="待发货", courier=None, waybill=None, amount=1299.0),
            Order(order_no="ORD20240507-005", product_name="手机壳 Pro", status="已发货", courier="京东物流", waybill="JD111222333", amount=49.0),
        ]
        session.add_all(orders)

    # 优惠券
    result = await session.execute(select(sqlfunc.count(Coupon.id)))
    if result.scalar() == 0:
        from datetime import date as dt_date
        coupons = [
            Coupon(code="JAN100", description="满100减20", threshold=100.0, discount=20.0, expire_date=dt_date(2026, 12, 31)),
            Coupon(code="NEW50", description="新用户满50减10", threshold=50.0, discount=10.0, expire_date=dt_date(2026, 6, 30)),
            Coupon(code="VIP200", description="VIP满200减50", threshold=200.0, discount=50.0, expire_date=dt_date(2026, 12, 31)),
            Coupon(code="SALE500", description="大促满500减100", threshold=500.0, discount=100.0, expire_date=dt_date(2026, 6, 18)),
            Coupon(code="FREE30", description="限时满30减5", threshold=30.0, discount=5.0, expire_date=dt_date(2026, 5, 31)),
        ]
        session.add_all(coupons)

    # 商品
    result = await session.execute(select(sqlfunc.count(Product.id)))
    if result.scalar() == 0:
        products = [
            Product(name="智能手机 X1", price=2999.0, stock=520, rating=4.8, category="手机数码"),
            Product(name="无线降噪耳机 Pro", price=599.0, stock=1200, rating=4.6, category="手机数码"),
            Product(name="轻薄笔记本 Air", price=5999.0, stock=85, rating=4.9, category="电脑办公"),
            Product(name="智能手表 S3", price=1299.0, stock=230, rating=4.5, category="智能穿戴"),
            Product(name="平板电脑 Pad+", price=3499.0, stock=150, rating=4.7, category="电脑办公"),
        ]
        session.add_all(products)

    # FAQ
    result = await session.execute(select(sqlfunc.count(FAQ.id)))
    if result.scalar() == 0:
        faqs = [
            FAQ(question="如何申请退货", answer="支持7天无理由退货，15天内质量问题可换货。请登录App→我的订单→选择订单→申请退货，填写原因后提交，客服24小时内审核。", category="售后", priority=10),
            FAQ(question="退货政策", answer="支持7天无理由退货，15天内质量问题可换货，运费由商家承担。退回商品需保持原包装完整，不影响二次销售。", category="售后", priority=10),
            FAQ(question="发货时效", answer="下单后48小时内发货，节假日顺延。通常情况下，预计3-5个工作日送达，偏远地区可能需要7-10个工作日。", category="物流", priority=8),
            FAQ(question="多久能到货", answer="下单后48小时内发货，预计3-5个工作日送达。具体时效因地区和物流公司而异，可在订单详情页查看物流进度。", category="物流", priority=8),
            FAQ(question="如何开具发票", answer="支持电子发票和纸质发票。电子发票在签收后24小时内发送至您注册邮箱，也可在订单详情页下载。纸质发票随包裹寄出。", category="发票", priority=5),
            FAQ(question="发票怎么开", answer="在提交订单时可选择开具发票，支持个人或企业抬头。电子发票在签收后24小时内发送至邮箱，纸质发票随包裹寄出。", category="发票", priority=5),
            FAQ(question="售后维修流程", answer="全国联保，质保期内免费维修。可通过App在线申请售后或致电400-888-8888。携带购机发票至就近授权服务中心。", category="售后", priority=8),
            FAQ(question="退款什么时候到账", answer="退款申请审核通过后，预计3-5个工作日退回原支付账户。信用卡/花呗退款可能需7-15个工作日，具体以银行到账时间为准。", category="售后", priority=7),
            FAQ(question="如何修改收货地址", answer="未发货订单可在订单详情页修改地址。已发货订单需联系快递公司或在线客服修改。您也可以输入「转人工」获取即时帮助。", category="订单", priority=6),
            FAQ(question="商品质量问题怎么办", answer="签收后发现质量问题，请拍照保存证据，在订单详情页申请售后。7天内可退货，15天内可换货，质保期内可维修。", category="售后", priority=9),
            FAQ(question="如何联系人工客服", answer="您可以在对话框输入「转人工」或「人工客服」，系统会为您转接人工客服。人工客服工作时间：每天9:00-21:00。", category="客服", priority=10),
            FAQ(question="快递丢失如何处理", answer="如快递超过7天未更新物流信息，请立即联系客服处理。核实丢失后，我们将安排补发或全额退款，同时向快递公司发起索赔。", category="物流", priority=7),
        ]
        session.add_all(faqs)

    await session.commit()
