# Use the official PostgreSQL image as a base
#FROM 142496269814.dkr.ecr.us-west-2.amazonaws.com/postgres:16
FROM postgres:16

# Set the working directory
WORKDIR /migrations

# Copy migration scripts
COPY migrations/*.sql /migrations/

# Add a shell script to execute the SQL files in order
RUN { \
    echo '#!/bin/bash'; \
    echo 'export PGPASSWORD="$POSTGRES_PASSWORD"'; \
    echo 'for file in $(ls -v /migrations/*.sql); do'; \
    echo '    echo "Executing $file...";'; \
    echo '    psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -h "$POSTGRES_HOST" --set ON_ERROR_STOP=on -f "$file" || exit 1;'; \
    echo '    echo "Finished executing $file";'; \
    echo 'done'; \
} > /execute-migrations.sh

# Make the script executable
RUN chmod +x /execute-migrations.sh

# Set the script as the entrypoint
ENTRYPOINT ["/execute-migrations.sh"]
