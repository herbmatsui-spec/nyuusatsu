# alembic/env.py
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
import sys
import os

# プロジェクトルートをパスに追加
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ここでモデルをインポートしてメタデータを登録
from database.models import Base
from database.models._generated import Base as GeneratedBase

# modelsのBaseと_generatedのBaseは同じものなので、どちらか一方を使用
target_metadata = Base.metadata

# 設定読み込み
config = context.config

# ログ設定
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def get_database_url():
    """データベースURLを環境変数またはデフォルトから取得"""
    # 環境変数から取得
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return database_url
    # デフォルト: SQLite
    return "sqlite:///./bids_system.db"


def run_migrations_offline() -> None:
    """オフラインモードでマイグレーション実行"""
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """オンラインモードでマイグレーション実行"""
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = get_database_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()