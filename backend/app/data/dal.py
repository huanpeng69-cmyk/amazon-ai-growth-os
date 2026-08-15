"""Data Access Layer —— Agent 唯一取数入口。

取数顺序：先查 DB 缓存（products / reviews / keyword_metrics / ad_metrics / image_assets）
→ 缺失则触发 Connector.fetch → Data Processing 解析 → 落 raw_fetches + 领域表 → 返回领域模型。
force_refresh=True 时忽略缓存，重新回源。

所有 Agent 禁止直接调用 random / 外部 API / 编造数据；一律经本模块。
"""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy.orm import Session

from app.data.connectors import ConnectorRegistry
from app.data.exceptions import ConnectorError, DataNotFound
from app.data.models import (
    AdRecord,
    ImageRecord,
    KeywordRecord,
    ProductRecord,
    ReviewRecord,
)
from app.data.processing import (
    parse_ads,
    parse_images,
    parse_keywords,
    parse_products,
    parse_reviews,
)
from app.data.schemas import (
    AdData,
    ImageData,
    KeywordData,
    MarketSignal,
    ProductData,
    ReviewItem,
)


# ───────────────────────── Product ─────────────────────────
def list_products(db: Session, keyword: Optional[str] = None, country: str = "US",
                  force_refresh: bool = False) -> List[ProductData]:
    """返回匹配关键词的商品列表（经 Connector → Processing → DB 缓存）。"""
    raw = ConnectorRegistry.get("amazon").fetch({"keyword": keyword, "country": country})
    parsed = parse_products(raw.model_dump())
    _persist_products(db, parsed, source=raw.source)
    return parsed


def get_product(db: Session, asin: Optional[str] = None, keyword: Optional[str] = None,
                country: str = "US", force_refresh: bool = False) -> ProductData:
    if asin and not force_refresh:
        rec = db.query(ProductRecord).filter_by(asin=asin, country=country).first()
        if rec:
            return _rec_to_product(rec)
    products = list_products(db, keyword=keyword, country=country, force_refresh=force_refresh)
    if asin:
        for p in products:
            if p.asin == asin:
                return p
    return products[0]


def _rec_to_product(rec: ProductRecord) -> ProductData:
    return ProductData(
        asin=rec.asin, country=rec.country, title=rec.title, price=rec.price,
        bsr=rec.bsr, est_monthly_sales=rec.est_monthly_sales, sellers=rec.sellers,
        rating=rec.rating, review_count=rec.review_count, category=rec.category,
    )


def _persist_products(db: Session, items: List[ProductData], source: str) -> None:
    for it in items:
        rec = db.query(ProductRecord).filter_by(asin=it.asin, country=it.country).first()
        if not rec:
            rec = ProductRecord(asin=it.asin, country=it.country)
        rec.title = it.title
        rec.price = it.price
        rec.bsr = it.bsr
        rec.est_monthly_sales = it.est_monthly_sales
        rec.sellers = it.sellers
        rec.rating = it.rating
        rec.review_count = it.review_count
        rec.category = it.category
        rec.source = source
        db.add(rec)
    db.commit()


# ───────────────────────── Reviews ─────────────────────────
def get_reviews(db: Session, asin: str, country: str = "US", max_reviews: int = 200,
                force_refresh: bool = False) -> List[ReviewItem]:
    if not force_refresh:
        recs = db.query(ReviewRecord).filter_by(asin=asin, country=country).all()
        if recs:
            return [_rec_to_review(r) for r in recs][:max_reviews]
    try:
        raw = ConnectorRegistry.get("review").fetch({"asin": asin, "country": country})
    except ConnectorError:
        return []  # 次级数据缺失不中断主流程
    parsed = parse_reviews(raw.model_dump())[:max_reviews]
    _persist_reviews(db, asin, country, parsed, source=raw.source)
    return parsed


def _rec_to_review(rec: ReviewRecord) -> ReviewItem:
    return ReviewItem(
        rating=rec.rating, body=rec.body, is_vp=rec.is_vp,
        reviewed_at=rec.reviewed_at, pain_keywords=list(rec.pain_keywords or []),
    )


def _persist_reviews(db: Session, asin: str, country: str, items: List[ReviewItem], source: str) -> None:
    # 简单策略：刷新时清旧写新
    db.query(ReviewRecord).filter_by(asin=asin, country=country).delete()
    for it in items:
        db.add(ReviewRecord(
            asin=asin, country=country, rating=it.rating, body=it.body,
            is_vp=it.is_vp, reviewed_at=it.reviewed_at,
            pain_keywords=list(it.pain_keywords), source=source,
        ))
    db.commit()


# ───────────────────────── Keywords ─────────────────────────
def get_keyword(db: Session, seed_keyword: str, country: str = "US",
                force_refresh: bool = False) -> List[KeywordData]:
    if not force_refresh:
        recs = db.query(KeywordRecord).filter_by(seed_keyword=seed_keyword, country=country).all()
        if recs:
            return [_rec_to_keyword(r) for r in recs]
    try:
        raw = ConnectorRegistry.get("keyword").fetch({"seed_keyword": seed_keyword, "country": country})
    except ConnectorError:
        return []  # 次级数据缺失不中断主流程
    parsed = parse_keywords(raw.model_dump())
    _persist_keywords(db, seed_keyword, country, parsed, source=raw.source)
    return parsed


def _rec_to_keyword(rec: KeywordRecord) -> KeywordData:
    return KeywordData(
        keyword=rec.keyword, search_volume=rec.search_volume, competition=rec.competition,
        cpc=rec.cpc, trend=rec.trend,
    )


def _persist_keywords(db: Session, seed: str, country: str, items: List[KeywordData], source: str) -> None:
    db.query(KeywordRecord).filter_by(seed_keyword=seed, country=country).delete()
    for it in items:
        db.add(KeywordRecord(
            seed_keyword=seed, country=country, keyword=it.keyword,
            search_volume=it.search_volume, competition=it.competition,
            cpc=it.cpc, trend=it.trend, source=source,
        ))
    db.commit()


# ───────────────────────── Ads ─────────────────────────
def get_ads(db: Session, asin: Optional[str] = None, country: str = "US",
            force_refresh: bool = False) -> AdData:
    if asin and not force_refresh:
        rec = db.query(AdRecord).filter_by(asin=asin, country=country).first()
        if rec:
            return _rec_to_ad(rec)
    raw = ConnectorRegistry.get("ads").fetch({"asin": asin, "country": country})
    parsed = parse_ads(raw.model_dump())
    _persist_ads(db, asin, country, parsed, source=raw.source)
    return parsed


def _rec_to_ad(rec: AdRecord) -> AdData:
    return AdData(
        acos=rec.acos, roas=rec.roas, ctr=rec.ctr, cvr=rec.cvr, spend=rec.spend,
        ad_sales=rec.ad_sales, orders=rec.orders,
        period_start=rec.period_start, period_end=rec.period_end,
    )


def _persist_ads(db: Session, asin: Optional[str], country: str, it: AdData, source: str) -> None:
    rec = db.query(AdRecord).filter_by(asin=asin, country=country).first()
    if not rec:
        rec = AdRecord(asin=asin, country=country)
    rec.acos = it.acos
    rec.roas = it.roas
    rec.ctr = it.ctr
    rec.cvr = it.cvr
    rec.spend = it.spend
    rec.ad_sales = it.ad_sales
    rec.orders = it.orders
    rec.period_start = it.period_start
    rec.period_end = it.period_end
    rec.source = source
    db.add(rec)
    db.commit()


# ───────────────────────── Images ─────────────────────────
def get_images(db: Session, asin: Optional[str] = None, query: Optional[str] = None,
               kind: str = "reference", force_refresh: bool = False) -> List[ImageData]:
    if not force_refresh:
        q = db.query(ImageRecord).filter_by(kind=kind)
        if asin:
            q = q.filter_by(asin=asin)
        recs = q.all()
        if recs:
            return [_rec_to_image(r) for r in recs]
    raw = ConnectorRegistry.get("image").fetch({"asin": asin, "query": query, "kind": kind})
    parsed = parse_images(raw.model_dump())
    _persist_images(db, asin, parsed, source=raw.source)
    return parsed


def _rec_to_image(rec: ImageRecord) -> ImageData:
    return ImageData(url=rec.url, width=rec.width, height=rec.height, kind=rec.kind, source=rec.source)


def _persist_images(db: Session, asin: Optional[str], items: List[ImageData], source: str) -> None:
    for it in items:
        db.add(ImageRecord(
            kind=it.kind, asin=asin, url=it.url, width=it.width,
            height=it.height, source=it.source,
        ))
    db.commit()


# ───────────────────────── Market 聚合（蓝海挖掘） ─────────────────────────
def _estimate_growth_yoy(reviews: int, price: float) -> float:
    """基于评论热度与价格带估算年增速代理值（0.0 ~ 0.45）。
    高评论量 + 中低价带 → 高增长大众赛道；低评论/高价 → 成熟/小众赛道。"""
    if reviews <= 0 and price <= 0:
        return 0.05
    heat = min(reviews / 10000.0, 1.0)
    if price <= 0:
        price_factor = 0.5
    elif 10 <= price <= 50:
        price_factor = 1.0
    elif 50 < price <= 100:
        price_factor = 0.8
    else:
        price_factor = 0.6
    return round(min(heat * price_factor * 0.45, 0.45), 3)


def get_market(db: Session, country: str, category: str,
               force_refresh: bool = False) -> List[MarketSignal]:
    """由 amazon + keyword + review 三个 Connector 聚合出市场信号（无随机编造）。"""
    products = list_products(db, keyword=category, country=country, force_refresh=force_refresh)
    # 关键词搜索量按 niche（category）聚合，所有商品共用，只需取一次
    kw = get_keyword(db, seed_keyword=category, country=country, force_refresh=force_refresh)
    search_volume = kw[0].search_volume if kw else None
    signals: List[MarketSignal] = []
    for p in products:
        # 评论痛点聚合
        pains: List[dict] = []
        if p.asin:
            reviews = get_reviews(db, asin=p.asin, country=country, force_refresh=force_refresh)
            counter: dict = {}
            for r in reviews:
                for pk in r.pain_keywords:
                    counter[pk] = counter.get(pk, 0) + 1
            pains = [{"pain": k, "evidence": v} for k, v in
                     sorted(counter.items(), key=lambda x: -x[1])[:4]]
        signals.append(MarketSignal(
            country=country,
            category=p.category,
            niche_keyword=category,
            product_name=p.title,
            search_volume_monthly=search_volume,
            avg_price_usd=p.price,
            num_sellers=p.sellers,
            avg_reviews=p.review_count,
            growth_yoy=_estimate_growth_yoy(p.review_count or 0, p.price or 0),
            pain_points=pains,
        ))
    return signals


def get_fee_schedule(country: str = "US") -> dict:
    """平台费率表（FBA / 佣金）。当前为占位默认；Phase 5 起由 amazon_connector 提供真实费率。"""
    return {
        "referral_fee_rate": 0.15,
        "fba_fee": 3.5,
        "note": "占位默认费率；接入真实 Amazon 费率表后由 amazon_connector 提供",
    }
