"""Auto-generated SQLAlchemy models from bids_system.db + bids.db schema."""
from sqlalchemy import Column, Integer, String, Text, Float, LargeBinary, Boolean, DateTime, Numeric, ForeignKey, Enum as SQLEnum, Date
from sqlalchemy.orm import declarative_base, relationship
import enum
from datetime import datetime
Base = declarative_base()

class Agency(Base):
    __tablename__ = 'agencies'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    type = Column(String, )
    region = Column(String, )
    base_url = Column(String, )
    bid_url_pattern = Column(String, )
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)
    municipality_code = Column(String, )
    category_id = Column(Integer, ForeignKey('agency_categories.id'))
    priority_level = Column(Integer, )
    system_type = Column(Text, )
    parent_id = Column(Integer, ForeignKey('agencies.id', name='fk_agencies_parent_id'), nullable=True, index=True)
    parent = relationship("Agency", remote_side=[id], back_populates="children")
    children = relationship("Agency", back_populates="parent")
    backfill_jobs = relationship("BackfillJob", back_populates="agency")


class AgencyInventory(Base):
    __tablename__ = 'agency_inventory'

    id = Column(Integer, primary_key=True, autoincrement=True)
    agency_name = Column(String(255), nullable=False, index=True)
    prefecture_code = Column(String(2), nullable=False, index=True)
    municipality = Column(String(128), nullable=True)
    top_page_url = Column(String(1024), nullable=True)
    bid_page_url = Column(String(1024), nullable=True)
    page_format = Column(String(16), nullable=False, default="unknown")
    is_crawled = Column(Boolean, default=False)
    crawler_config_id = Column(Integer, ForeignKey("crawl_configs.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AgencyCategory(Base):
    __tablename__ = 'agency_categories'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(String, )
    priority = Column(Integer, nullable=False)

class AlembicVersion(Base):
    __tablename__ = 'alembic_version'
    version_num = Column(String, primary_key=True)

class AlertHistory(Base):
    __tablename__ = 'alert_history'
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, nullable=False)
    component = Column(String, nullable=False)
    severity = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    resolved_at = Column(DateTime, )

class AuditLog(Base):
    __tablename__ = 'audit_logs'
    id = Column(Integer, primary_key=True)
    user_id = Column(String, )
    action = Column(String, nullable=False)
    resource_type = Column(String, )
    resource_id = Column(Integer, )
    ip = Column(String, )
    detail_json = Column(Text, )
    created_at = Column(DateTime, nullable=False, default='CURRENT_TIMESTAMP')

class AwardHistory(Base):
    __tablename__ = 'award_histories'
    id = Column(Integer, primary_key=True)
    competitor_id = Column(Integer, ForeignKey('competitors.id'), nullable=False)
    award_result_id = Column(Integer, ForeignKey('award_results.id'), nullable=False)
    rank = Column(Integer, )
    bid_amount = Column(Integer, )
    is_winner = Column(Boolean, nullable=False)
    created_at = Column(DateTime, nullable=False)

class AwardResult(Base):
    __tablename__ = 'award_results'
    id = Column(Integer, primary_key=True)
    tender_id = Column(Integer, ForeignKey('bids.id'))
    source_url = Column(String, )
    agency_name = Column(String, )
    category = Column(String, )
    project_name = Column(String, )
    budget_amount = Column(Integer, )
    contract_amount = Column(Integer, )
    award_rate = Column(Float, )
    winner_name = Column(String, )
    winner_count = Column(Integer, )
    announcement_date = Column(DateTime, )
    award_date = Column(DateTime, )
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)
    winner_normalized = Column(String, )
    fiscal_year = Column(Integer, )
    is_rebidding = Column(Boolean, nullable=False)

class BidAssignment(Base):
    __tablename__ = 'bid_assignments'
    id = Column(Integer, primary_key=True)
    bid_id = Column(Integer, ForeignKey('bids.id'), nullable=False)
    user_id = Column(String, )
    role = Column(String, )
    assigned_at = Column(DateTime, nullable=False, default='CURRENT_TIMESTAMP')

class BidQualificationTag(Base):
    __tablename__ = 'bid_qualification_tags'
    bid_id = Column(Integer, ForeignKey('bids.id'), primary_key=True)
    tag_id = Column(Integer, ForeignKey('qualification_tags.id'), nullable=False)
    is_required = Column(Boolean, nullable=False)
    raw_text = Column(Text, )
    required_grade = Column(String, )
    required_region = Column(String, )

class BidSource(Base):
    __tablename__ = 'bid_sources'
    id = Column(Integer, primary_key=True)
    prefecture_id = Column(Integer, ForeignKey('prefectures.id'), nullable=False)
    source_type = Column(String, nullable=False)
    url = Column(String, nullable=False)
    url_pattern = Column(String, )
    parser_type = Column(String, nullable=False)
    css_selectors = Column(Text, )
    requires_login = Column(Boolean, nullable=False)
    username = Column(String, )
    password = Column(String, )
    last_crawled_at = Column(DateTime, )
    crawl_interval_hours = Column(Integer, nullable=False)
    is_active = Column(Boolean, nullable=False)
    notes = Column(Text, )
    created_at = Column(DateTime, default='CURRENT_TIMESTAMP')
    updated_at = Column(DateTime, default='CURRENT_TIMESTAMP')

class BidStatus(Base):
    __tablename__ = 'bid_statuses'
    id = Column(Integer, primary_key=True)
    bid_id = Column(Integer, ForeignKey('bids.id'), nullable=False)
    status = Column(String, nullable=False)
    changed_at = Column(DateTime, nullable=False)
    changed_by = Column(String, )
    memo = Column(Text, )

class Bid(Base):
    __tablename__ = 'bids'
    id = Column(Integer, primary_key=True)
    filename = Column(String, nullable=False)
    source_url = Column(String, )
    analyzed_at = Column(DateTime, nullable=False)
    budget = Column(String, )
    qualifications = Column(Text, )
    deadline = Column(String, )
    deliverables = Column(Text, )
    key_risks = Column(Text, )
    notes = Column(Text, )
    current_status = Column(String, nullable=False)
    industry_category = Column(String, )
    organization_name = Column(String, )
    bid_type = Column(String, nullable=True)
    actual_bid_amount = Column(Integer, )
    win_loss_reason = Column(Text, )
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)
    budget_amount = Column(Integer, )
    awarded_company = Column(String, )
    awarded_date = Column(DateTime, )
    award_rate = Column(Float, )
    prefecture_code = Column(String, )
    announcement_date = Column(DateTime, )
    updated_date = Column(DateTime, )
    delivery_deadline = Column(Date, )
    specification_text = Column(Text, )
    specification_text_clean = Column(Text, )
    bid_difficulty_score = Column(Float, )
    win_prediction_score = Column(Float, )

class CompanyProfile(Base):
    __tablename__ = 'company_profiles'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    unified_qualification_grade = Column(String, )
    unified_qualification_number = Column(String, )
    unified_qualification_expire = Column(DateTime, )
    industry_category = Column(String, )
    region = Column(String, )
    memo = Column(String, )
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

class CompanyRegionRank(Base):
    __tablename__ = 'company_region_ranks'
    id = Column(Integer, primary_key=True)
    company_profile_id = Column(Integer, ForeignKey('company_profiles.id'), nullable=False)
    prefecture_code = Column(String, nullable=False)
    region_rank = Column(String, )
    category = Column(String, )
    expire_date = Column(DateTime, )
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

class CompetitorAlertConfig(Base):
    __tablename__ = 'competitor_alert_configs'
    id = Column(Integer, primary_key=True)
    competitor_id = Column(Integer, ForeignKey('competitors.id'), nullable=False)
    industry_category = Column(String, )
    min_budget = Column(Integer, nullable=False)
    is_active = Column(Boolean, nullable=False)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

class Competitor(Base):
    __tablename__ = 'competitors'
    id = Column(Integer, primary_key=True)
    normalized_name = Column(String, nullable=False)
    raw_names = Column(String, )
    corporate_number = Column(String, )
    industry_category = Column(String, )
    region = Column(String, )
    website = Column(String, )
    is_target_company = Column(Boolean, nullable=False)
    memo = Column(String, )
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)
    corporate_type = Column(String, )

class CrawlConfig(Base):
    __tablename__ = 'crawl_configs'
    id = Column(Integer, primary_key=True)
    agency_id = Column(Integer, ForeignKey('agencies.id'), nullable=False)
    target_url = Column(String, nullable=False)
    parser_type = Column(String, nullable=False)
    frequency = Column(String, nullable=False)
    is_active = Column(Boolean, nullable=False)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

class CrawlHistory(Base):
    __tablename__ = 'crawl_history'
    id = Column(Integer, primary_key=True)
    crawl_time = Column(DateTime, nullable=False)
    url_count = Column(Integer, nullable=False)
    new_count = Column(Integer, nullable=False)
    status = Column(String, nullable=False)
    error_message = Column(Text, )

class CrawlJob(Base):
    __tablename__ = 'crawl_jobs'
    id = Column(Integer, primary_key=True)
    prefecture_id = Column(Integer, ForeignKey('prefectures.id'), nullable=False)
    job_type = Column(String, nullable=False)
    status = Column(String, nullable=False)
    started_at = Column(DateTime, )
    finished_at = Column(DateTime, )
    bid_count_found = Column(Integer, nullable=False)
    bid_count_new = Column(Integer, nullable=False)
    bid_count_updated = Column(Integer, nullable=False)
    error_message = Column(Text, )
    log_path = Column(String, )
    created_at = Column(DateTime, default='CURRENT_TIMESTAMP')

class CrawlLog(Base):
    __tablename__ = 'crawl_logs'
    id = Column(Integer, primary_key=True)
    agency_id = Column(Integer, ForeignKey('agencies.id'), nullable=False)
    crawled_at = Column(DateTime, nullable=False)
    status = Column(String, nullable=False)
    error_message = Column(Text, )
    new_bids_count = Column(Integer, nullable=False)

class CrawledUrl(Base):
    __tablename__ = 'crawled_urls'
    id = Column(Integer, primary_key=True)
    url = Column(String, nullable=False)
    title = Column(String, )
    found_time = Column(DateTime, nullable=False)
    notified = Column(Boolean, )

class CustomerBidLink(Base):
    __tablename__ = 'customer_bid_links'
    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey('customers.id'), nullable=False)
    bid_id = Column(Integer, ForeignKey('bids.id'), nullable=False)
    linked_at = Column(DateTime, nullable=False)
    memo = Column(Text, )

class Customer(Base):
    __tablename__ = 'customers'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    email = Column(String, )
    phone = Column(String, )
    company = Column(String, )
    memo = Column(Text, )
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

class DocumentArchive(Base):
    __tablename__ = 'document_archives'
    id = Column(Integer, primary_key=True)
    bid_id = Column(Integer, ForeignKey('bids.id'))
    file_type = Column(String, nullable=False)
    original_url = Column(String, )
    local_path = Column(String, nullable=False)
    sha256 = Column(String, )
    file_size = Column(Integer, )
    archived_at = Column(DateTime, nullable=False)
    is_deleted_external = Column(Boolean, nullable=False)
    metadata_json = Column(Text, )
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

class ExtractionResult(Base):
    __tablename__ = 'extraction_results'
    id = Column(Integer, primary_key=True)
    filename = Column(String, nullable=False)
    budget = Column(String, )
    qualifications = Column(Text, )
    deadline = Column(String, )
    deliverables = Column(Text, )
    raw_text_length = Column(Integer, nullable=False)
    created_by = Column(String, )
    created_at = Column(DateTime, nullable=False)
    bid_id = Column(Integer, )
    question_deadline = Column(DateTime, )
    submit_deadline = Column(DateTime, )
    opening_date = Column(DateTime, )

class Favorite(Base):
    __tablename__ = 'favorites'
    id = Column(Integer, primary_key=True)
    bid_id = Column(Integer, ForeignKey('bids.id'), nullable=False)
    user_id = Column(String, nullable=False)
    favorited_at = Column(DateTime, nullable=False)
    memo = Column(Text, )

class ForecastStatus(Base):
    __tablename__ = 'forecast_statuses'
    id = Column(Integer, primary_key=True)
    forecast_id = Column(Integer, ForeignKey('procurement_forecasts.id'), nullable=False)
    status = Column(String, nullable=False)
    changed_at = Column(DateTime, nullable=False)
    changed_by = Column(String, )
    memo = Column(Text, )

class NotificationChannel(Base):
    __tablename__ = 'notification_channels'
    id = Column(Integer, primary_key=True)
    user_id = Column(String, )
    channel_type = Column(String, nullable=False)
    webhook_url = Column(String, )
    email_address = Column(String, )
    is_active = Column(Boolean, nullable=False, default='1')
    created_at = Column(DateTime, nullable=False, default='CURRENT_TIMESTAMP')
    updated_at = Column(DateTime, nullable=False, default='CURRENT_TIMESTAMP')

class Organization(Base):
    __tablename__ = 'organizations'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    code = Column(String, )
    parent_id = Column(Integer, ForeignKey('organizations.id'))
    created_at = Column(DateTime, nullable=False, default='CURRENT_TIMESTAMP')

class PartnerBidLink(Base):
    __tablename__ = 'partner_bid_links'
    id = Column(Integer, primary_key=True)
    partner_id = Column(Integer, ForeignKey('partners.id'), nullable=False)
    bid_id = Column(Integer, ForeignKey('bids.id'), nullable=False)
    linked_at = Column(DateTime, nullable=False)
    memo = Column(Text, )

class Partner(Base):
    __tablename__ = 'partners'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    category = Column(String, )
    contact = Column(String, )
    memo = Column(Text, )
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

class PdfDocument(Base):
    __tablename__ = 'pdf_documents'
    id = Column(Integer, primary_key=True)
    url = Column(String, nullable=False)
    filename = Column(String, nullable=False)
    sha256 = Column(String, nullable=False)
    file_size = Column(Integer, nullable=False)
    downloaded_at = Column(DateTime, nullable=False)
    agency_id = Column(Integer, ForeignKey('agencies.id'))

class PipelineMetric(Base):
    __tablename__ = 'pipeline_metrics'
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, nullable=False)
    stage = Column(String, nullable=False)
    metric_name = Column(String, nullable=False)
    metric_value = Column(Float, nullable=False)
    labels = Column(Text, )
    trace_id = Column(String, )

class PipelineRun(Base):
    __tablename__ = 'pipeline_runs'
    id = Column(Integer, primary_key=True)
    run_id = Column(String, nullable=False)
    agency_id = Column(Integer, )
    agency_name = Column(String, )
    status = Column(String, nullable=False)
    total_items = Column(Integer, )
    processed_items = Column(Integer, )
    failed_items = Column(Integer, )
    started_at = Column(DateTime, default='CURRENT_TIMESTAMP')
    completed_at = Column(DateTime, )
    error_message = Column(String, )

class Prefecture(Base):
    __tablename__ = 'prefectures'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    code = Column(String, nullable=False)
    kana_name = Column(String, nullable=False)
    region_code = Column(String, )
    is_active = Column(Boolean, nullable=False)
    priority = Column(Integer, nullable=False)
    official_url = Column(String, )
    created_at = Column(DateTime, default='CURRENT_TIMESTAMP')
    updated_at = Column(DateTime, default='CURRENT_TIMESTAMP')

class PricePrediction(Base):
    __tablename__ = 'price_predictions'
    id = Column(Integer, primary_key=True)
    bid_id = Column(Integer, ForeignKey('bids.id'))
    competitor_ids_json = Column(Text, )
    bid_amount = Column(Integer, )
    expected_price = Column(Integer, )
    win_probability = Column(Float, )
    rationale = Column(Text, )
    created_at = Column(DateTime, nullable=False, default='CURRENT_TIMESTAMP')

class ProcurementForecast(Base):
    __tablename__ = 'procurement_forecasts'
    id = Column(Integer, primary_key=True)
    agency_id = Column(Integer, ForeignKey('agencies.id'), nullable=False)
    fiscal_year = Column(Integer, nullable=False)
    quarter = Column(Integer, )
    title = Column(String, nullable=False)
    description = Column(Text, )
    estimated_budget = Column(String, )
    estimated_budget_amount = Column(Integer, )
    expected_publish_date = Column(DateTime, )
    expected_bid_date = Column(DateTime, )
    category = Column(String, )
    industry_category = Column(String, )
    source_url = Column(String, )
    pdf_url = Column(String, )
    status = Column(String, nullable=False)
    priority_level = Column(String, )
    notes = Column(Text, )
    related_bid_id = Column(Integer, ForeignKey('bids.id'))
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)
    last_crawled_at = Column(DateTime, )

class QualificationTag(Base):
    __tablename__ = 'qualification_tags'
    id = Column(Integer, primary_key=True)
    tag_code = Column(String, nullable=False)
    display_name = Column(String, nullable=False)
    category = Column(String, )
    description = Column(Text, )
    grade_required = Column(String, )
    region_required = Column(String, )
    is_unified_qualification = Column(Boolean, nullable=False, default="'0'")
    compatible_grades = Column(String, )

class Role(Base):
    __tablename__ = 'roles'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    permissions_json = Column(Text, )
    created_at = Column(DateTime, nullable=False, default='CURRENT_TIMESTAMP')

class SavedSearch(Base):
    __tablename__ = 'saved_searches'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    name = Column(String, nullable=False)
    criteria_json = Column(Text, nullable=False)
    last_notified_at = Column(DateTime, )
    is_active = Column(Boolean, nullable=False, default='1')
    created_at = Column(DateTime, nullable=False, default='CURRENT_TIMESTAMP')
    updated_at = Column(DateTime, nullable=False, default='CURRENT_TIMESTAMP')

class SearchHistory(Base):
    __tablename__ = 'search_history'
    id = Column(Integer, primary_key=True)
    query = Column(String, nullable=False)
    filters = Column(Text, )
    results_count = Column(Integer, nullable=False)
    searched_at = Column(DateTime, nullable=False)

class Setting(Base):
    __tablename__ = 'settings'
    key = Column(String, primary_key=True)
    value = Column(Text, nullable=False)

class UrlRegistry(Base):
    __tablename__ = 'url_registry'
    id = Column(Integer, primary_key=True)
    municipality_code = Column(String, nullable=False)
    agency_name = Column(String, nullable=False)
    base_url = Column(String, nullable=False)
    search_url = Column(String, )
    category_id = Column(Integer, ForeignKey('agency_categories.id'))
    parser_type = Column(String, nullable=False)
    max_depth = Column(Integer, nullable=False)
    last_crawled_at = Column(String, )
    parent_id = Column(Integer, ForeignKey('url_registry.id', name='fk_url_registry_parent_id'), nullable=True, index=True)
    parent = relationship("UrlRegistry", remote_side=[id], back_populates="children")
    children = relationship("UrlRegistry", back_populates="parent")

class UserRole(Base):
    __tablename__ = 'user_roles'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    role_id = Column(Integer, ForeignKey('roles.id'), nullable=False)
    scope = Column(String, )
    created_at = Column(DateTime, nullable=False, default='CURRENT_TIMESTAMP')

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    username = Column(String, nullable=False)
    email = Column(String, )
    password_hash = Column(String, )
    org_id = Column(Integer, ForeignKey('organizations.id'))
    is_active = Column(Boolean, nullable=False, default='1')
    created_at = Column(DateTime, nullable=False, default='CURRENT_TIMESTAMP')
    plan = Column(String(20), default='free', nullable=False)
    stripe_customer_id = Column(String(100), unique=True, nullable=True)
    stripe_subscription_id = Column(String(100), unique=True, nullable=True)
    trial_ends_at = Column(DateTime, nullable=True)
    subscription_status = Column(String(20), default='inactive', nullable=False)
    current_period_end = Column(DateTime, nullable=True)
    allowed_prefectures = Column(Text, nullable=True)


class BackfillJobStatus(str, enum.Enum):
    """バックフィルジョブのステータス"""
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"


class BackfillJob(Base):
    """バックフィル実行ジョブ"""
    __tablename__ = 'backfill_jobs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    agency_id = Column(Integer, ForeignKey('agencies.id'), nullable=False, index=True)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    status = Column(SQLEnum(BackfillJobStatus), nullable=False, default=BackfillJobStatus.PENDING, index=True)
    fetched_count = Column(Integer, nullable=False, default=0)
    new_count = Column(Integer, nullable=False, default=0)
    updated_count = Column(Integer, nullable=False, default=0)
    error_count = Column(Integer, nullable=False, default=0)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    agency = relationship("Agency", back_populates="backfill_jobs")
    logs = relationship("BackfillJobLog", back_populates="job", cascade="all, delete-orphan")


class BackfillJobLog(Base):
    """バックフィルジョブ実行ログ"""
    __tablename__ = 'backfill_job_logs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Integer, ForeignKey('backfill_jobs.id'), nullable=False, index=True)
    step = Column(String(100), nullable=False)
    message = Column(Text, nullable=False)
    level = Column(String(20), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    job = relationship("BackfillJob", back_populates="logs")

