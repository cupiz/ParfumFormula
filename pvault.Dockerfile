FROM jbparfum/perfumersvault:latest

# Switch to root to ensure we can write to /var/www/html
USER root

# Copy custom updated files directly into the image
# Paths are relative to project root (../)
COPY pages/listIngredients.php /var/www/html/pages/listIngredients.php
COPY js/autosearch.js /var/www/html/js/autosearch.js
COPY api-functions/ingredient_autosearch.php /var/www/html/api-functions/ingredient_autosearch.php

# FORCE Fix to allow running FPM as root (since www-data is broken/missing)
RUN echo "[www]" > /etc/php-fpm.d/z-force-user.conf && \
    echo "user = root" >> /etc/php-fpm.d/z-force-user.conf && \
    echo "group = root" >> /etc/php-fpm.d/z-force-user.conf

# IMPORTANT: We must OVERRIDE the entrypoint to pass the -R flag to php-fpm
# Looking at original image, entrypoint.sh likely executes php-fpm at the end.
# We will create a wrapper entrypoint
COPY docker-compose/entrypoint_wrapper.sh /entrypoint_wrapper.sh
RUN chmod +x /entrypoint_wrapper.sh

ENTRYPOINT ["/entrypoint_wrapper.sh"]

# Ensure files are readable
RUN chmod 644 /var/www/html/pages/listIngredients.php \
    /var/www/html/js/autosearch.js \
    /var/www/html/api-functions/ingredient_autosearch.php
