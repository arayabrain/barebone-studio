#!/bin/bash
set -e

echo 'Starting container'
echo 'Attempting to connect to RDS'
echo "DB_HOST: ${DB_HOST}"
echo "DB_USER: ${DB_USER}"
echo "DB_NAME: ${DB_NAME}"

# Wait for RDS to be available
max_tries=30
counter=0
until mysql -h "${DB_HOST}" -u "${DB_USER}" -p"${DB_PASSWORD}" "${DB_NAME}" -e 'SELECT 1;'
do
    sleep 2
    [[ counter -eq $max_tries ]] && echo "Failed to connect to Database" && exit 1
    echo "Attempt $counter: Waiting for Database..."
    ((counter++))
done

echo 'Database connection successful'

# Run database migrations
alembic upgrade head

# Check load balancer (consider removing this if not necessary)
if [ -n "$AWS_SERVICE_URL" ]; then
    (
        max_tries=30
        counter=0
        until curl -s -o /dev/null --max-time 10 "$AWS_SERVICE_URL"
        do
            sleep 10
            [[ counter -eq $max_tries ]] && echo "Load balancer not ready after 5 minutes" && break
            echo "Attempt $counter: Waiting for load balancer..."
            ((counter++))
        done
        if [ $counter -lt $max_tries ]; then
            echo "Load balancer is ready"
        fi
    ) &
else
    echo "Please provide 'AWS_SERVICE_URL' environment variables"
    exit 1
fi

echo "Host: $BACKEND_HOST"
echo "Port: $BACKEND_PORT"

if [ -z "$BACKEND_HOST" ] || [ -z "$BACKEND_PORT" ]; then
    echo "Please provide 'BACKEND_HOST' and 'BACKEND_PORT' environment variables"
    exit 1
fi

# Start the application
exec poetry run python main.py --host="$BACKEND_HOST" --port="$BACKEND_PORT"