-- Create the apps table to store application information
CREATE TABLE IF NOT EXISTS apps (
    id SERIAL PRIMARY KEY,
    app VARCHAR(255) NOT NULL,
    status VARCHAR(255) NOT NULL,
    payload JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_activity_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT unique_app_name UNIQUE (app),
    -- Check constraint for valid status values
    CONSTRAINT valid_status CHECK (
        status IN (
            'APPROVING QUIESCE',
            'COMPLETED',
            'CREATED',
            'DEPLOY FAILED',
            'DEPLOYED',
            'DEPLOYING',
            'FLUSHING',
            'HALT',
            'NOT ENOUGH SERVERS',
            'QUIESCED',
            'QUIESCING',
            'RECOVERING SOURCES',
            'RUNNING',
            'STARTING',
            'STARTING SOURCES',
            'STOPPED',
            'STOPPING',
            'TERMINATED',
            'UNKNOWN',
            'VERIFYING STARTING'
        )
    );
);


-- Create an index on the app column for faster lookups
CREATE INDEX IF NOT EXISTS idx_app_status_app_name ON apps (app);

-- Create the queue table to store apps that need monitoring
CREATE TABLE IF NOT EXISTS _queue (
    id SERIAL PRIMARY KEY,
    app_id INT REFERENCES apps(id),
    app VARCHAR(255) NOT NULL,
    app_uri VARCHAR(255),
    status VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT unique_app_name_queue UNIQUE (app)
);

-- Create an index on the app column for faster lookups
CREATE INDEX IF NOT EXISTS idx_queue_app_name ON _queue (app);

-- Create a function to update the updated_at and last_activity_at timestamps
CREATE OR REPLACE FUNCTION update_timestamps() RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    NEW.last_activity_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create a trigger to automatically update the timestamps before insert or update
CREATE TRIGGER trigger_update_timestamps BEFORE INSERT OR UPDATE ON apps FOR EACH ROW EXECUTE FUNCTION update_timestamps();

-- Function to remove inactive apps after 30 days
CREATE OR REPLACE FUNCTION remove_inactive_apps() RETURNS VOID AS $$
BEGIN
    DELETE FROM apps
    WHERE last_activity_at < NOW() - INTERVAL '30 days'
    -- AND status NOT IN ('FAILED', 'DEPLOY FAILED', 'HALT', 'TERMINATED');
END;
$$ LANGUAGE plpgsql;

-- Function to remove all apps
CREATE OR REPLACE FUNCTION remove_all_finished_apps() RETURNS VOID AS $$
BEGIN
    DELETE FROM apps;
END;
$$ LANGUAGE plpgsql;

-- Wrapper function to decide which action to take
CREATE OR REPLACE FUNCTION cleanup(criteria VARCHAR(255)) RETURNS VOID AS $$
BEGIN
    IF criteria = 'inactive_after_30_days' THEN
        PERFORM remove_inactive_apps();
    ELSIF criteria = 'remove_all' THEN
        PERFORM remove_all_finished_apps();
    ELSE
        RAISE EXCEPTION 'Invalid criteria provided';
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Function to queue applications with nodowntime_app in payload
CREATE OR REPLACE FUNCTION queue_nodowntime_apps() RETURNS VOID AS $$
BEGIN
    -- Insert relevant 'nodowntime_app' applications into the queue
    INSERT INTO _queue (app_id, app, app_uri, status, created_at)
    SELECT DISTINCT ON (a.app)
        a.id,
        a.app,
        a.app_uri,
        'PENDING',
        NOW()
    FROM apps a
    WHERE a.payload ? 'nodowntime_app'
    AND NOT EXISTS (
        SELECT 1
        FROM _queue q
        WHERE q.app = a.app
    )
    AND EXISTS (
        SELECT 1
        FROM historic_metrics h
        WHERE h.app_id = a.id
        AND h.status = 'COMPLETED'
        AND h.timestamp >= NOW() - INTERVAL '7 days'
    );
END;
$$ LANGUAGE plpgsql;

-- Create the historic_metrics table to store incremental historic metrics
CREATE TABLE IF NOT EXISTS historic_metrics (
    id SERIAL PRIMARY KEY,
    app_id INT REFERENCES apps(id),
    status VARCHAR(255) NOT NULL,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT valid_timestamp CHECK (timestamp >= NOW() - INTERVAL '60 days')
);

-- Create an index on app_id and status columns for faster lookups
CREATE INDEX IF NOT EXISTS idx_historic_metrics_app_id ON historic_metrics (app_id);
CREATE INDEX IF NOT EXISTS idx_historic_metrics_status ON historic_metrics (status);

-- Historic metrics by status view
CREATE OR REPLACE VIEW historic_metrics_by_status AS
SELECT status,
    DATE_TRUNC('day', timestamp) AS day,
    COUNT(*) AS count
FROM historic_metrics
GROUP BY status,
    day
ORDER BY status,
    day;

-- Historic metrics by time view
CREATE OR REPLACE VIEW historic_metrics_by_time AS
SELECT DATE_TRUNC('day', timestamp) AS day,
    COUNT(*) AS count
FROM historic_metrics
GROUP BY day
ORDER BY day;

-- Status lineage by app_id view
CREATE OR REPLACE VIEW status_lineage_by_app AS
SELECT app_id,
       status,
       timestamp AS start_time,
       LEAD(timestamp) OVER (PARTITION BY app_id ORDER BY timestamp) AS end_time
FROM historic_metrics
ORDER BY app_id, timestamp;
