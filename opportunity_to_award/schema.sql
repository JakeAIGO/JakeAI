-- JakeAI Opportunity-to-Award Engine - Phase 1
-- Canonical PostgreSQL/JSONB schema transcribed from the Council-approved v1.0 artifact.
-- Commercial fee terms remain PENDING_LEGAL_REVIEW and MUST NOT trigger invoicing.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS contractors (
    contractor_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_name VARCHAR(255) NOT NULL,
    dba_name VARCHAR(255),
    corporate_headquarters JSONB NOT NULL,
    primary_contact JSONB NOT NULL,
    estimating_desk JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(50) DEFAULT 'ACTIVE'
);

CREATE TABLE IF NOT EXISTS contractor_licenses (
    license_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contractor_id UUID REFERENCES contractors(contractor_id) ON DELETE CASCADE,
    state VARCHAR(2) NOT NULL,
    license_number VARCHAR(100) NOT NULL,
    classification VARCHAR(100) NOT NULL,
    expiration_date DATE NOT NULL,
    status VARCHAR(50) DEFAULT 'VERIFIED',
    verification_source VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS contractor_bonding_insurance (
    bonding_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contractor_id UUID REFERENCES contractors(contractor_id) ON DELETE CASCADE,
    surety_company VARCHAR(255) NOT NULL,
    surety_agent JSONB NOT NULL,
    single_project_limit NUMERIC(15,2) NOT NULL,
    aggregate_limit NUMERIC(15,2) NOT NULL,
    available_capacity NUMERIC(15,2) NOT NULL,
    emr_rating NUMERIC(4,2) NOT NULL,
    gl_occurrence NUMERIC(15,2) NOT NULL,
    umbrella_limit NUMERIC(15,2) NOT NULL,
    last_verified_date DATE NOT NULL
);

CREATE TABLE IF NOT EXISTS contractor_scopes_certifications (
    cert_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contractor_id UUID REFERENCES contractors(contractor_id) ON DELETE CASCADE,
    system_category VARCHAR(100) NOT NULL,
    membrane_types TEXT[],
    manufacturer_credentials JSONB NOT NULL,
    certified_install_years INT NOT NULL,
    in_house_sheet_metal_shop BOOLEAN DEFAULT FALSE,
    in_house_crane_rigging BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS agency_prequalifications (
    prequal_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contractor_id UUID REFERENCES contractors(contractor_id) ON DELETE CASCADE,
    agency_name VARCHAR(255) NOT NULL,
    agency_code VARCHAR(100),
    prequal_status VARCHAR(50) NOT NULL,
    expiration_date DATE NOT NULL,
    approved_dollar_threshold NUMERIC(15,2)
);

CREATE TABLE IF NOT EXISTS contractor_operational_capacity (
    capacity_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contractor_id UUID REFERENCES contractors(contractor_id) ON DELETE CASCADE,
    service_radius_miles INT NOT NULL DEFAULT 100,
    active_field_crews INT NOT NULL,
    concurrent_project_capacity INT NOT NULL,
    current_active_commitments INT NOT NULL,
    target_project_min_val NUMERIC(15,2) DEFAULT 250000.00,
    target_project_max_val NUMERIC(15,2) DEFAULT 5000000.00,
    public_works_experience_years INT NOT NULL
);

CREATE TABLE IF NOT EXISTS commercial_terms_agreements (
    agreement_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contractor_id UUID REFERENCES contractors(contractor_id) ON DELETE CASCADE,
    agreement_version VARCHAR(50) NOT NULL,
    signed_date TIMESTAMPTZ,
    signer_name VARCHAR(255),
    signer_title VARCHAR(100),
    fee_structure VARCHAR(50) NOT NULL,
    fee_percentage NUMERIC(5,2) DEFAULT 5.00,
    terms_status VARCHAR(50) DEFAULT 'PENDING_LEGAL_REVIEW',
    anti_circumvention_period_months INT DEFAULT 24
);

-- JakeAI integration extensions. These are not represented as canonical tables in the v1.0 source artifact;
-- they implement the required audit/provenance and permanent human-approval release gate.
CREATE TABLE IF NOT EXISTS opportunity_to_award_release_gates (
    gate_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    opportunity_id VARCHAR(255) NOT NULL,
    action_type VARCHAR(100) NOT NULL,
    requested_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    approved_at TIMESTAMPTZ,
    approved_by VARCHAR(255),
    status VARCHAR(50) NOT NULL DEFAULT 'PENDING_HUMAN_APPROVAL',
    CHECK (status IN ('PENDING_HUMAN_APPROVAL','APPROVED','REJECTED','EXPIRED'))
);

CREATE TABLE IF NOT EXISTS opportunity_to_award_distribution_receipts (
    receipt_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    opportunity_id VARCHAR(255) NOT NULL,
    contractor_id UUID REFERENCES contractors(contractor_id) ON DELETE RESTRICT,
    package_version VARCHAR(100) NOT NULL,
    delivered_at TIMESTAMPTZ,
    acknowledged_at TIMESTAMPTZ,
    sha256_receipt CHAR(64) NOT NULL UNIQUE,
    release_gate_id UUID REFERENCES opportunity_to_award_release_gates(gate_id) ON DELETE RESTRICT
);
