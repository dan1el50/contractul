FROM node:22-alpine

WORKDIR /app

# Dependencies in their own layer, so editing source does not reinstall them.
# The lockfile is copied when present (the * makes it optional on first run)
# and `npm ci` is used when it is, for reproducible installs.
COPY package.json package-lock.json* ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

COPY . .

EXPOSE 5173

# Development overrides this. See docker-compose.override.yml.
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
