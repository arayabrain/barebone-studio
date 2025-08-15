#!/bin/bash
set -e  # Exit immediately if a command exits with a non-zero status

# Map infrastructure environment variables (DB_*) to application expected variables (MYSQL_*)
# This allows the application's config.py to find the correct environment variables
# while maintaining infrastructure naming conventions
export MYSQL_SERVER="${DB_HOST}"
export MYSQL_USER="${DB_USER}"
export MYSQL_PASSWORD="${DB_PASSWORD}"
export MYSQL_DATABASE="${DB_NAME}"

echo 'Starting container'
echo 'Attempting to connect to RDS'
# Log environment variables for debugging
echo "DB_HOST: ${MYSQL_SERVER}"
echo "DB_USER: ${MYSQL_USER}"
echo "DB_NAME: ${MYSQL_DATABASE}"

# Wait for RDS to be available
# This is necessary because RDS might still be initializing when container starts
# Tries 30 times with 2 second intervals (total 60 seconds timeout)
max_tries=30
counter=0
until mysql --skip-ssl -h "${MYSQL_SERVER}" -u "${MYSQL_USER}" -p"${MYSQL_PASSWORD}" "${MYSQL_DATABASE}" -e 'SELECT 1;'
do
    sleep 2
    [[ counter -eq $max_tries ]] && echo "Failed to connect to Database" && exit 1
    echo "Attempt $counter: Waiting for Database..."
    ((counter++))
done

echo 'Database connection successful'

# Create database if it doesn't exist
# This ensures the application's database exists before proceeding
mysql --skip-ssl -h "$MYSQL_SERVER" -u "$MYSQL_USER" -p"$MYSQL_PASSWORD" <<-EOSQL
    CREATE DATABASE IF NOT EXISTS ${MYSQL_DATABASE};
    USE ${MYSQL_DATABASE};
EOSQL

if ! mysql --skip-ssl -h "$MYSQL_SERVER" -u "$MYSQL_USER" -p"$MYSQL_PASSWORD" -e "USE ${MYSQL_DATABASE}"; then
    echo "Failed to create/access database ${MYSQL_DATABASE}"
    exit 1
fi

echo "Database ${MYSQL_DATABASE} ready"

# Run database migrations using alembic
# This ensures all database tables and schemas are up to date
cd /app
alembic upgrade head

# Initialize subscription plans
echo "Initializing subscription plans..."
mysql --skip-ssl -h "$MYSQL_SERVER" -u "$MYSQL_USER" -p"$MYSQL_PASSWORD" ${MYSQL_DATABASE} <<-EOSQL
    INSERT IGNORE INTO subscription_plans (id, name, price, billing_cycle, currency, status)
    VALUES (1, 'Free', 0, 30, 840, 1), (2, 'Premium', 2999, 30, 840, 1);
EOSQL

# Initialize tax rates
echo "Initializing tax rates..."
mysql --skip-ssl -h "$MYSQL_SERVER" -u "$MYSQL_USER" -p"$MYSQL_PASSWORD" ${MYSQL_DATABASE} <<-EOSQL
    INSERT IGNORE INTO taxes (tax_type, tax_name, tax_rate, is_active, effective_date)
    VALUES ('sales_tax', 'Sales Tax', 0.10, 1, CURDATE());
EOSQL

# Initialize admin user and organization
# Only proceeds if all required environment variables are set
# This section handles first-time setup of the application
if [ ! -z "$INITIAL_FIREBASE_UID" ] && [ ! -z "$INITIAL_USER_NAME" ] && [ ! -z "$INITIAL_USER_EMAIL" ]; then
    echo "Checking for existing admin user..."
    # Check if user already exists to prevent duplicate creation
    USER_EXISTS=$(mysql --skip-ssl -h "$MYSQL_SERVER" -u "$MYSQL_USER" -p"$MYSQL_PASSWORD" -N -s -e \
        "SELECT COUNT(*) FROM ${MYSQL_DATABASE}.users WHERE uid='$INITIAL_FIREBASE_UID';")

    if [ "$USER_EXISTS" -eq "0" ]; then
        # Create default organization first (required due to foreign key constraint)
        echo "Creating default organization..."
        mysql --skip-ssl -h "$MYSQL_SERVER" -u "$MYSQL_USER" -p"$MYSQL_PASSWORD" ${MYSQL_DATABASE} <<-EOSQL
            INSERT IGNORE INTO organization (id, name) VALUES (1, 'Default Organization');
EOSQL

        # Create the initial admin user
        echo "Creating initial admin user..."
        mysql --skip-ssl -h "$MYSQL_SERVER" -u "$MYSQL_USER" -p"$MYSQL_PASSWORD" ${MYSQL_DATABASE} <<-EOSQL
            INSERT INTO users (uid, organization_id, name, email, active)
            VALUES ('$INITIAL_FIREBASE_UID', 1, '$INITIAL_USER_NAME', '$INITIAL_USER_EMAIL', true);
EOSQL
        echo "Initial admin user created successfully"

        # Initialize storage usage for admin user
        if [ ! -z "$ADMIN_STORAGE_QUOTA_BYTES" ]; then
            echo "Initializing admin user storage quota..."
            mysql --skip-ssl -h "$MYSQL_SERVER" -u "$MYSQL_USER" -p"$MYSQL_PASSWORD" ${MYSQL_DATABASE} <<-EOSQL
                INSERT IGNORE INTO user_storage_usage (user_id, current_usage_bytes, quota_limit_bytes)
                VALUES (1, 0, $ADMIN_STORAGE_QUOTA_BYTES);
EOSQL
            echo "Admin user storage quota initialized: $ADMIN_STORAGE_QUOTA_BYTES bytes"
        else
            echo "ADMIN_STORAGE_QUOTA_BYTES not provided, skipping storage quota initialization"
        fi

        # Set admin user to premium plan
        echo "Setting admin user to premium plan..."
        mysql --skip-ssl -h "$MYSQL_SERVER" -u "$MYSQL_USER" -p"$MYSQL_PASSWORD" ${MYSQL_DATABASE} <<-EOSQL
            INSERT IGNORE INTO subscription_users (plan_id, user_id, expiration)
            VALUES (2, 1, DATE_ADD(NOW(), INTERVAL 365 DAY));
EOSQL
        echo "Admin user set to premium plan"
    else
        echo "Admin user already exists, skipping creation"
    fi
fi

# Verify backend configuration
# Ensures required environment variables are set before starting the application
echo "Host: $BACKEND_HOST"
echo "Port: $BACKEND_PORT"
if [ -z "$BACKEND_HOST" ] || [ -z "$BACKEND_PORT" ]; then
    echo "Please provide 'BACKEND_HOST' and 'BACKEND_PORT' environment variables"
    exit 1
fi

# Start the application in background
echo "Starting application..."
poetry run python main.py --host="$BACKEND_HOST" --port="$BACKEND_PORT" &
APP_PID=$!

# Allow initial startup time matching ECS health check startPeriod
echo "Waiting for initial startup..."
sleep 30

# Single initial health check before load balancer check
echo "Verifying initial health..."
if ! curl -v "http://${BACKEND_HOST}:${BACKEND_PORT}/health"; then
    echo "Initial health check failed"
    # Don't exit - let ECS handle it
fi

# Load balancer health check function
# Verifies that the application is accessible through the load balancer
check_load_balancer() {
    if [ -n "$AWS_SERVICE_URL" ]; then
        echo "Checking load balancer status..."
        readonly MAX_TRIES=30
        readonly WAIT_SECONDS=10
        local counter=0

        # Try for 5 minutes (30 attempts * 10 seconds)
        until curl -s -o /dev/null --max-time ${WAIT_SECONDS} "$AWS_SERVICE_URL"
        do
            sleep ${WAIT_SECONDS}
            [[ $counter -eq $MAX_TRIES ]] && echo "Load balancer not ready after 5 minutes" && return 1
            echo "Attempt $counter: Waiting for load balancer..."
            ((counter++))
        done
        echo "Load balancer is ready"
        return 0
    else
        echo "AWS_SERVICE_URL not provided, skipping load balancer check"
        return 0
    fi
}

# Run load balancer check in background
# This allows parallel checking while the application is starting
check_load_balancer &
LB_CHECK_PID=$!

# Wait for all background processes to complete
# This ensures the container keeps running as long as the application is running
wait $APP_PID
wait $LB_CHECK_PID
