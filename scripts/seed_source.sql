-- Runs AFTER 001-init.sql. Switch into the source database we just created and
-- load ~400 synthetic support tickets. All data is fake and non-sensitive.
\connect source_data

CREATE TABLE IF NOT EXISTS support_tickets (
    id         SERIAL PRIMARY KEY,
    subject    TEXT NOT NULL,
    body       TEXT NOT NULL,
    product    TEXT NOT NULL,
    status     TEXT NOT NULL,
    priority   TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

-- Generate 400 rows by combining 20 recurring "themes" (subject + matching body)
-- with a rotating set of products, statuses, priorities, and customer names, plus
-- a random creation date within the last 180 days. Using generate_series keeps the
-- seed compact instead of 400 hand-written INSERTs.
WITH params AS (
    SELECT
        ARRAY[
            'Cannot log in after password reset',
            'Two-factor authentication code never arrives',
            'Payment declined at checkout',
            'Charged twice for the same order',
            'Requesting a refund for a duplicate charge',
            'App crashes immediately on startup',
            'Pages load very slowly and time out',
            'File upload fails with an error',
            'Not receiving email notifications',
            'CSV export produces an empty file',
            'Data does not sync between my devices',
            'Feature request: add a dark mode',
            'API returns 500 errors intermittently',
            'Webhook events are not being delivered',
            'My account was locked unexpectedly',
            'Cannot update my email address',
            'Subscription upgrade was not applied',
            'Missing invoices in billing history',
            'Search returns no results for valid terms',
            'Slack integration stopped working'
        ] AS subjects,
        ARRAY[
            'the user completed a password reset but the new password is rejected on the login screen',
            'the verification code for two-factor authentication is never received by SMS or email',
            'the card payment is declined at checkout even though the card is valid and has funds',
            'the customer was billed twice for a single purchase and wants the extra charge reversed',
            'a duplicate charge appeared on the statement and the customer is requesting a refund',
            'the application closes instantly on launch and never reaches the home screen',
            'navigation between pages is extremely slow and some requests time out completely',
            'uploading an attachment fails partway through with a generic upload error',
            'expected email alerts and notifications are not arriving in the inbox or spam folder',
            'exporting records to a CSV file downloads a file that contains no rows',
            'changes made on one device do not appear on the other devices after syncing',
            'the customer would like a dark colour theme to reduce eye strain at night',
            'the public endpoints occasionally respond with internal server errors under load',
            'configured webhooks are not firing when the related events occur',
            'the account was suspended without warning and the user cannot sign in',
            'attempts to change the profile email address are not saved and revert back',
            'after upgrading the subscription plan the new limits and features are still not active',
            'past invoices are missing from the billing history and cannot be downloaded',
            'searching for known existing items returns an empty result set',
            'messages are no longer posted to the connected Slack workspace'
        ] AS bodies,
        ARRAY['Web App', 'Mobile App', 'Public API', 'Billing Portal', 'Desktop Client'] AS products,
        ARRAY['open', 'pending', 'resolved', 'closed'] AS statuses,
        ARRAY['low', 'medium', 'high', 'urgent'] AS priorities,
        ARRAY['Ada', 'Blake', 'Chen', 'Diego', 'Emeka', 'Farah', 'Grace', 'Hiro', 'Ivy', 'Jonas'] AS customers
)
INSERT INTO support_tickets (subject, body, product, status, priority, created_at)
SELECT
    p.subjects[1 + (g % 20)],
    p.customers[1 + (g % array_length(p.customers, 1))] || ' reports that '
        || p.bodies[1 + (g % 20)]
        || ' (Product: ' || p.products[1 + (g % array_length(p.products, 1))]
        || ', ref #' || g || ').',
    p.products[1 + (g % array_length(p.products, 1))],
    p.statuses[1 + (g % array_length(p.statuses, 1))],
    p.priorities[1 + (g % array_length(p.priorities, 1))],
    now() - (random() * interval '180 days')
FROM generate_series(1, 400) AS g, params AS p;
