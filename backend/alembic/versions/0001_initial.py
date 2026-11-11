"""schema inicial: drivers, positions, job_runs

Revision ID: 0001
Revises:
Create Date: 2026-11-04
"""
import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "drivers",
        sa.Column("driver_id", sa.String(), primary_key=True),
        sa.Column("first_seen", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "positions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("driver_id", sa.String(), sa.ForeignKey("drivers.driver_id"), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_positions_driver_time", "positions", ["driver_id", sa.text("recorded_at DESC")])

    op.create_table(
        "job_runs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("job_name", sa.String(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("detail", sa.String(), nullable=True),
    )
    op.create_index("idx_job_runs_name_started", "job_runs", ["job_name", sa.text("started_at DESC")])


def downgrade() -> None:
    op.drop_table("job_runs")
    op.drop_table("positions")
    op.drop_table("drivers")
