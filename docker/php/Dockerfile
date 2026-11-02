ARG PHP_VER=8.2
FROM php:${PHP_VER}-fpm-alpine

# Install git, bash, zip tools
RUN apk add --no-cache bash git curl unzip

# Install extension helper mlocati
ADD https://github.com/mlocati/docker-php-extension-installer/releases/latest/download/install-php-extensions /usr/local/bin/
RUN chmod +x /usr/local/bin/install-php-extensions && \
    install-php-extensions \
      pdo_mysql \
      pdo_pgsql \
      mysqli \
      zip \
      bcmath \
      intl \
      gd \
      redis \
      opcache \
      pcntl \
      exif

# Copy Composer binary dari image official composer
COPY --from=composer:latest /usr/bin/composer /usr/bin/composer
