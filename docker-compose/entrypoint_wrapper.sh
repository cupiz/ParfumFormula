#!/bin/bash

# Modify the original entrypoint to include -R flag if it calls php-fpm
# But we don't know the exact original entrypoint script name or content easily without inspecting.
# Instead, we will hack the php-fpm binary to always include -R

if [ ! -f /usr/sbin/php-fpm.bak ]; then
    mv /usr/sbin/php-fpm /usr/sbin/php-fpm.bak
    echo '#!/bin/bash' > /usr/sbin/php-fpm
    echo 'exec /usr/sbin/php-fpm.bak -R "$@"' >> /usr/sbin/php-fpm
    chmod +x /usr/sbin/php-fpm
fi

# Pass control to the original entrypoint logic (which likely runs the app)
# We assume the base image just runs a script or command.
# If base image has ENTRYPOINT ["/entrypoint.sh"] and CMD ["php-fpm"],
# we need to execute that.

# Let's try to execute the original command passed to CMD
exec "$@"
