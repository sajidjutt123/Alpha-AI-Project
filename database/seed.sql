-- Alpha AI — development seed (Pakistani market, PKR prices)
--
-- Run as an ADMIN connection (bypasses RLS):
--   python -m app.db.migrate --seed
--
-- Idempotent: fixed UUIDs + ON CONFLICT DO NOTHING.
-- Two organizations exist on purpose — to demonstrate tenant isolation.

-- ===========================================================================
-- Organizations
-- ===========================================================================
INSERT INTO organizations (id, name, slug) VALUES
    ('11111111-1111-4111-8111-111111111111', 'Alpha Estates', 'alpha-estates'),
    ('22222222-2222-4222-8222-222222222222', 'Galaxy Properties', 'galaxy-properties')
ON CONFLICT (id) DO NOTHING;

-- ===========================================================================
-- Agents
-- auth_user_id links each agent to a Supabase Auth user (dev/demo tokens).
-- ===========================================================================
INSERT INTO agents (id, organization_id, name, email, phone, role, auth_user_id) VALUES
    ('11111111-1111-4111-8111-000000000101', '11111111-1111-4111-8111-111111111111',
     'Ahmed Raza', 'ahmed@alphaestates.pk', '+923001234500', 'OWNER',
     '11111111-1111-4111-8111-00000000a101'),
    ('11111111-1111-4111-8111-000000000102', '11111111-1111-4111-8111-111111111111',
     'Fatima Khan', 'fatima@alphaestates.pk', '+923001234501', 'AGENT',
     '11111111-1111-4111-8111-00000000a102'),
    ('11111111-1111-4111-8111-000000000103', '11111111-1111-4111-8111-111111111111',
     'Usman Ali', 'usman@alphaestates.pk', '+923001234502', 'AGENT',
     '11111111-1111-4111-8111-00000000a103'),
    ('22222222-2222-4222-8222-000000000201', '22222222-2222-4222-8222-222222222222',
     'Hassan Sheikh', 'hassan@galaxyproperties.pk', '+92211234500', 'OWNER',
     '22222222-2222-4222-8222-00000000a201'),
    ('22222222-2222-4222-8222-000000000202', '22222222-2222-4222-8222-222222222222',
     'Zara Iqbal', 'zara@galaxyproperties.pk', '+92211234501', 'AGENT',
     '22222222-2222-4222-8222-00000000a202')
ON CONFLICT (id) DO NOTHING;

-- ===========================================================================
-- Properties — Alpha Estates (Lahore)
-- ===========================================================================
INSERT INTO properties (id, organization_id, title, description, price, location,
                        property_type, bedrooms, bathrooms, area, availability) VALUES
    ('11111111-1111-4111-8111-000000000110', '11111111-1111-4111-8111-111111111111',
     '5 Marla Designer House — DHA Phase 6',
     'Brand new designer build, imported fittings, corner plot near Commercial Broadway.',
     32500000, 'DHA Phase 6, Lahore', 'HOUSE', 3, 4, 1350, 'AVAILABLE'),
    ('11111111-1111-4111-8111-000000000111', '11111111-1111-4111-8111-111111111111',
     '10 Marla House — DHA Phase 5',
     'Well-maintained family home in a quiet block, landscaped lawn, double garage.',
     68000000, 'DHA Phase 5, Lahore', 'HOUSE', 5, 6, 2420, 'AVAILABLE'),
    ('11111111-1111-4111-8111-000000000112', '11111111-1111-4111-8111-111111111111',
     '1 Kanal Luxury House — Bahria Town',
     'Spanish-style villa with basement, smart-home wiring, park-facing.',
     115000000, 'Bahria Town, Lahore', 'HOUSE', 6, 7, 4680, 'AVAILABLE'),
    ('11111111-1111-4111-8111-000000000113', '11111111-1111-4111-8111-111111111111',
     '3 Bed Apartment — Gulberg III',
     'Serviced apartment near MM Alam Road, generator backup, two parking bays.',
     14500000, 'Gulberg III, Lahore', 'APARTMENT', 3, 3, 1650, 'AVAILABLE'),
    ('11111111-1111-4111-8111-000000000114', '11111111-1111-4111-8111-111111111111',
     '2 Bed Apartment — Bahria Orchard',
     'Affordable starter home, close to school and commercial area.',
     8900000, 'Bahria Orchard, Lahore', 'APARTMENT', 2, 2, 1050, 'RESERVED'),
    ('11111111-1111-4111-8111-000000000115', '11111111-1111-4111-8111-111111111111',
     '5 Marla Plot — DHA Phase 9 Prism',
     'Level plot in a fast-appreciating block, possession available.',
     9800000, 'DHA Phase 9 Prism, Lahore', 'PLOT', NULL, NULL, 1125, 'AVAILABLE'),
    ('11111111-1111-4111-8111-000000000116', '11111111-1111-4111-8111-111111111111',
     '1 Kanal Plot — Bahria Sector C',
     'Corner plot on 120-ft boulevard, ideal for custom build.',
     28000000, 'Bahria Town Sector C, Lahore', 'PLOT', NULL, NULL, 4500, 'AVAILABLE'),
    ('11111111-1111-4111-8111-000000000117', '11111111-1111-4111-8111-111111111111',
     'Commercial Plaza — Gulberg',
     'Four-floor commercial building, triple-height ground lobby, lift + staircase.',
     85000000, 'Gulberg II, Lahore', 'COMMERCIAL', NULL, 8, 5000, 'AVAILABLE')
ON CONFLICT (id) DO NOTHING;

-- Properties — Galaxy Properties (Karachi)
INSERT INTO properties (id, organization_id, title, description, price, location,
                        property_type, bedrooms, bathrooms, area, availability) VALUES
    ('22222222-2222-4222-8222-000000000210', '22222222-2222-4222-8222-222222222222',
     '4 Bed Apartment — Clifton Block 5',
     'Sea-facing apartment with servant quarter, dedicated parking.',
     42000000, 'Clifton Block 5, Karachi', 'APARTMENT', 4, 4, 2400, 'AVAILABLE'),
    ('22222222-2222-4222-8222-000000000211', '22222222-2222-4222-8222-222222222222',
     '500 Sq Yd House — DHA Phase 6 Karachi',
     'Recently renovated, Italian marble flooring, roof garden.',
     95000000, 'DHA Phase 6, Karachi', 'HOUSE', 6, 7, 4500, 'AVAILABLE'),
    ('22222222-2222-4222-8222-000000000212', '22222222-2222-4222-8222-222222222222',
     '8 Marla Plot — Bahria Town Karachi',
     'Plot near Grand Jamia mosque, clear transfer, immediate possession.',
     6500000, 'Bahria Town, Karachi', 'PLOT', NULL, NULL, 1800, 'AVAILABLE'),
    ('22222222-2222-4222-8222-000000000213', '22222222-2222-4222-8222-222222222222',
     'Commercial Floor — Tariq Road',
     'Whole floor suitable for showroom or offices, lift access.',
     60000000, 'Tariq Road, Karachi', 'COMMERCIAL', NULL, 4, 3200, 'AVAILABLE')
ON CONFLICT (id) DO NOTHING;

-- ===========================================================================
-- Leads — Alpha Estates
-- ===========================================================================
INSERT INTO leads (id, organization_id, name, phone, email, status, intent,
                   budget_min, budget_max, preferred_location, property_type,
                   bedrooms, urgency_score, qualification_score, summary,
                   assigned_agent_id) VALUES
    ('11111111-1111-4111-8111-000000000120', '11111111-1111-4111-8111-111111111111',
     'Ali Hassan', '+923001234567', 'ali.hassan@example.pk', 'QUALIFIED', 'BUY',
     25000000, 35000000, 'DHA Lahore', 'HOUSE', 4, 8, 82,
     'Serious buyer. Wants a ready 4-bed house in DHA Lahore within 35M; planning
      to visit next week. Prefers Phase 5-6.',
     '11111111-1111-4111-8111-000000000102'),
    ('11111111-1111-4111-8111-000000000121', '11111111-1111-4111-8111-111111111111',
     'Sara Ahmed', '+923217654321', NULL, 'CONTACTED', 'BUY',
     12000000, 16000000, 'Gulberg, Lahore', 'APARTMENT', 3, 6, 61,
     'Comparing Gulberg III vs Bahria Orchard. Investment + self-use.',
     '11111111-1111-4111-8111-000000000103'),
    ('11111111-1111-4111-8111-000000000122', '11111111-1111-4111-8111-111111111111',
     'Bilal Cheema', '+923339998877', NULL, 'NEW', 'BUY',
     8000000, 11000000, 'DHA Phase 9, Lahore', 'PLOT', NULL, 3, 45,
     NULL, NULL),
    ('11111111-1111-4111-8111-000000000123', '11111111-1111-4111-8111-111111111111',
     'Ayesha Malik', '+923451112233', 'ayesha.m@example.pk', 'CONVERTED', 'BUY',
     8000000, 10000000, 'Bahria Orchard, Lahore', 'APARTMENT', 2, 9, 91,
     'First-time buyer, booked 2-bed apartment in Bahria Orchard.',
     '11111111-1111-4111-8111-000000000102')
ON CONFLICT (id) DO NOTHING;

-- Lead — Galaxy Properties
INSERT INTO leads (id, organization_id, name, phone, email, status, intent,
                   budget_min, budget_max, preferred_location, property_type,
                   bedrooms, urgency_score, qualification_score, summary,
                   assigned_agent_id) VALUES
    ('22222222-2222-4222-8222-000000000220', '22222222-2222-4222-8222-222222222222',
     'Kamran Siddiqui', '+923017776655', NULL, 'CONTACTED', 'BUY',
     35000000, 45000000, 'Clifton, Karachi', 'APARTMENT', 4, 7, 74,
     'Relocating from Dubai in Q4; needs sea-view 4-bed in Clifton.',
     '22222222-2222-4222-8222-000000000202')
ON CONFLICT (id) DO NOTHING;

-- ===========================================================================
-- Messages — conversation transcript for Ali Hassan
-- ===========================================================================
INSERT INTO messages (id, lead_id, sender_type, content, channel, external_message_id) VALUES
    ('11111111-1111-4111-8111-000000000130', '11111111-1111-4111-8111-000000000120',
     'CUSTOMER', 'Assalam o Alaikum. I need a house in DHA Lahore.',
     'WHATSAPP', 'seed-msg-001'),
    ('11111111-1111-4111-8111-000000000131', '11111111-1111-4111-8111-000000000120',
     'AI', 'Wa Alaikum Assalam! Happy to help. May I ask your budget range and how many bedrooms you need?',
     'WHATSAPP', 'seed-msg-002'),
    ('11111111-1111-4111-8111-000000000132', '11111111-1111-4111-8111-000000000120',
     'CUSTOMER', 'Around 3 crore. Four bedrooms. Ready to move.',
     'WHATSAPP', 'seed-msg-003'),
    ('11111111-1111-4111-8111-000000000133', '11111111-1111-4111-8111-000000000120',
     'AI', 'I found three properties that match. The closest is a 10 Marla house in DHA Phase 5 at 6.8 crore — above your range. Within budget: a 5 Marla designer house in Phase 6 at 3.25 crore. Would you like details or a visit this week?',
     'WHATSAPP', 'seed-msg-004'),
    ('11111111-1111-4111-8111-000000000134', '11111111-1111-4111-8111-000000000120',
     'CUSTOMER', 'Send me the Phase 6 one please.',
     'WHATSAPP', 'seed-msg-005')
ON CONFLICT (id) DO NOTHING;

INSERT INTO messages (id, lead_id, sender_type, content, channel, external_message_id) VALUES
    ('11111111-1111-4111-8111-000000000135', '11111111-1111-4111-8111-000000000121',
     'CUSTOMER', 'Hi, do you have 3 bed apartments in Gulberg?',
     'WHATSAPP', 'seed-msg-006'),
    ('11111111-1111-4111-8111-000000000136', '11111111-1111-4111-8111-000000000121',
     'AI', 'Yes — a serviced 3-bed in Gulberg III at 1.45 crore near MM Alam Road. Is that within your budget, or should I also share options in Bahria Orchard?',
     'WHATSAPP', 'seed-msg-007')
ON CONFLICT (id) DO NOTHING;

-- ===========================================================================
-- Matches + AI runs
-- ===========================================================================
INSERT INTO lead_property_matches (id, lead_id, property_id, match_score, reason) VALUES
    ('11111111-1111-4111-8111-000000000140', '11111111-1111-4111-8111-000000000120',
     '11111111-1111-4111-8111-000000000110', 78,
     'Budget fit (32.5M within 25-35M), DHA Lahore as requested, ready to move; 1 bedroom short of ideal.'),
    ('11111111-1111-4111-8111-000000000141', '11111111-1111-4111-8111-000000000120',
     '11111111-1111-4111-8111-000000000111', 64,
     'Location and bedrooms match perfectly; price 6.8M above stated budget — finance-dependent.')
ON CONFLICT (id) DO NOTHING;

INSERT INTO ai_runs (id, lead_id, model, prompt_version, input_tokens, output_tokens, latency_ms) VALUES
    ('11111111-1111-4111-8111-000000000150', '11111111-1111-4111-8111-000000000120',
     'gpt-4o-mini', 'v1-seed', 1180, 264, 1450),
    ('11111111-1111-4111-8111-000000000151', '11111111-1111-4111-8111-000000000121',
     'gpt-4o-mini', 'v1-seed', 940, 210, 1210)
ON CONFLICT (id) DO NOTHING;
