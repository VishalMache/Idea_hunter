"""Add resumable pipeline state, stable clusters, and claim evidence.

Revision ID: a6b8d2e4f310
Revises: 9a4e5c7d1f20
"""

from alembic import op
import sqlalchemy as sa


revision = "a6b8d2e4f310"
down_revision = "9a4e5c7d1f20"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "clusters",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=True),
        sa.Column("state", sa.String(length=30), nullable=False, server_default="new"),
        sa.Column("centroid_metadata", sa.JSON(), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("observation_count", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_clusters_state_last_seen", "clusters", ["state", "last_seen_at"], unique=False)

    op.create_table(
        "pipeline_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=50), nullable=False, server_default="full"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("config_json", sa.JSON(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_cost_usd", sa.Float(), nullable=False, server_default="0"),
        sa.Column("budget_usd", sa.Float(), nullable=False, server_default="2"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_pipeline_run_idempotency_key"),
    )
    op.create_table(
        "run_steps",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("step_key", sa.String(length=100), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cost_usd", sa.Float(), nullable=False, server_default="0"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("output_json", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["pipeline_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "step_key", name="uq_run_step_key"),
    )
    op.create_index("ix_run_steps_run_id", "run_steps", ["run_id"], unique=False)

    op.create_table(
        "source_queries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("query_key", sa.String(length=255), nullable=False),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("config_json", sa.JSON(), nullable=True),
        sa.Column("last_seen_cursor", sa.String(length=512), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_id", "query_key", name="uq_source_query_key"),
    )
    op.create_index("ix_source_queries_source_id", "source_queries", ["source_id"], unique=False)

    op.add_column("observations", sa.Column("normalized_text", sa.Text(), nullable=True))
    op.add_column("observations", sa.Column("cluster_ref_id", sa.Integer(), nullable=True))
    op.add_column("observations", sa.Column("embedding_model", sa.String(length=255), nullable=True))
    op.add_column("observations", sa.Column("embedding_dimension", sa.Integer(), nullable=True))
    op.add_column("observations", sa.Column("embedding_state", sa.String(length=30), nullable=False, server_default="pending"))
    op.add_column("observations", sa.Column("embedding_attempts", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("observations", sa.Column("signal_type", sa.String(length=50), nullable=True))
    op.add_column("observations", sa.Column("triage_state", sa.String(length=30), nullable=False, server_default="pending"))
    op.add_column("observations", sa.Column("raw_payload_ref", sa.String(length=1024), nullable=True))
    op.create_foreign_key("fk_observations_cluster_ref", "observations", "clusters", ["cluster_ref_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_observations_cluster_ref_id", "observations", ["cluster_ref_id"], unique=False)

    op.create_table(
        "claims",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("problem_id", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("kind", sa.String(length=30), nullable=False, server_default="hypothesis"),
        sa.Column("support_state", sa.String(length=30), nullable=False, server_default="unverified"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["problem_id"], ["problems.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_claims_problem_id", "claims", ["problem_id"], unique=False)
    op.create_table(
        "claim_evidence",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("claim_id", sa.Integer(), nullable=False),
        sa.Column("observation_id", sa.Integer(), nullable=False),
        sa.Column("quote", sa.Text(), nullable=False),
        sa.Column("verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("stance", sa.String(length=30), nullable=False, server_default="support"),
        sa.ForeignKeyConstraint(["claim_id"], ["claims.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["observation_id"], ["observations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("claim_id", "observation_id", "quote", name="uq_claim_evidence_quote"),
    )
    op.create_index("ix_claim_evidence_claim_id", "claim_evidence", ["claim_id"], unique=False)
    op.create_index("ix_claim_evidence_observation_id", "claim_evidence", ["observation_id"], unique=False)

    op.create_table(
        "decisions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("problem_id", sa.Integer(), nullable=True),
        sa.Column("opportunity_id", sa.Integer(), nullable=True),
        sa.Column("actor", sa.String(length=255), nullable=False, server_default="local-user"),
        sa.Column("decision", sa.String(length=30), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["problem_id"], ["problems.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["opportunity_id"], ["opportunities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_decisions_problem_id", "decisions", ["problem_id"], unique=False)
    op.create_index("ix_decisions_opportunity_id", "decisions", ["opportunity_id"], unique=False)

    op.create_table(
        "model_registry",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("model", sa.String(length=255), nullable=False),
        sa.Column("dimension", sa.Integer(), nullable=True),
        sa.Column("input_cost_per_million", sa.Float(), nullable=False, server_default="0"),
        sa.Column("output_cost_per_million", sa.Float(), nullable=False, server_default="0"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "model", name="uq_model_registry_provider_model"),
    )
    op.create_table(
        "model_calls",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("pipeline_run_id", sa.Integer(), nullable=True),
        sa.Column("task", sa.String(length=100), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("model", sa.String(length=255), nullable=False),
        sa.Column("prompt_version", sa.String(length=100), nullable=True),
        sa.Column("schema_version", sa.String(length=100), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Float(), nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["pipeline_run_id"], ["pipeline_runs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_model_calls_pipeline_run_id", "model_calls", ["pipeline_run_id"], unique=False)

    op.add_column("opportunity_scores", sa.Column("potential", sa.Float(), nullable=True))
    op.add_column("opportunity_scores", sa.Column("confidence", sa.Float(), nullable=True))
    op.add_column("opportunity_scores", sa.Column("freshness_days", sa.Integer(), nullable=True))
    op.add_column("opportunity_scores", sa.Column("next_step", sa.String(length=100), nullable=True))
    op.add_column("opportunity_scores", sa.Column("scoring_version", sa.String(length=50), nullable=True))
    op.execute("UPDATE opportunity_scores SET potential = final_score, confidence = evidence_confidence, scoring_version = 'legacy-' || id::text")
    op.alter_column("opportunity_scores", "scoring_version", nullable=False, server_default="v2")
    op.create_unique_constraint("uq_opportunity_score_version", "opportunity_scores", ["opportunity_id", "scoring_version"])
    op.create_unique_constraint("uq_opportunity_problem_id", "opportunities", ["problem_id"])


def downgrade():
    op.drop_constraint("uq_opportunity_problem_id", "opportunities", type_="unique")
    op.drop_constraint("uq_opportunity_score_version", "opportunity_scores", type_="unique")
    op.drop_column("opportunity_scores", "scoring_version")
    op.drop_column("opportunity_scores", "next_step")
    op.drop_column("opportunity_scores", "freshness_days")
    op.drop_column("opportunity_scores", "confidence")
    op.drop_column("opportunity_scores", "potential")
    op.drop_index("ix_model_calls_pipeline_run_id", table_name="model_calls")
    op.drop_table("model_calls")
    op.drop_table("model_registry")
    op.drop_index("ix_decisions_opportunity_id", table_name="decisions")
    op.drop_index("ix_decisions_problem_id", table_name="decisions")
    op.drop_table("decisions")
    op.drop_index("ix_claim_evidence_observation_id", table_name="claim_evidence")
    op.drop_index("ix_claim_evidence_claim_id", table_name="claim_evidence")
    op.drop_table("claim_evidence")
    op.drop_index("ix_claims_problem_id", table_name="claims")
    op.drop_table("claims")
    op.drop_index("ix_observations_cluster_ref_id", table_name="observations")
    op.drop_constraint("fk_observations_cluster_ref", "observations", type_="foreignkey")
    for name in ("raw_payload_ref", "triage_state", "signal_type", "embedding_attempts", "embedding_state", "embedding_dimension", "embedding_model", "cluster_ref_id", "normalized_text"):
        op.drop_column("observations", name)
    op.drop_index("ix_source_queries_source_id", table_name="source_queries")
    op.drop_table("source_queries")
    op.drop_index("ix_run_steps_run_id", table_name="run_steps")
    op.drop_table("run_steps")
    op.drop_table("pipeline_runs")
    op.drop_index("ix_clusters_state_last_seen", table_name="clusters")
    op.drop_table("clusters")
