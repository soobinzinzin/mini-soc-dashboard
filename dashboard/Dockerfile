# =============================================================================
# Stage 1: Build static assets with Node.js
# =============================================================================
FROM node:20-alpine AS build

WORKDIR /app

# Copy dependency definitions
COPY package*.json ./

# Install dependencies
RUN npm ci || npm install

# Build-time environment variable (default: http://localhost:8000 for dev)
ARG VITE_API_URL=http://localhost:8000
ENV VITE_API_URL=$VITE_API_URL

# Copy source code
COPY . .

# Build production bundle
RUN npm run build

# =============================================================================
# Stage 2: Serve static files with Nginx
# =============================================================================
FROM nginx:alpine

# Remove default nginx config and static assets
RUN rm -rf /etc/nginx/conf.d/* /usr/share/nginx/html/*

# Copy custom nginx configuration for SPA
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy compiled static assets from build stage
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
