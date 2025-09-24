# Use Node.js to build the app
FROM node:18 AS build

WORKDIR /app

# Copy package files
COPY package*.json ./

RUN npm install

# Copy source
COPY . .

# Build the app (set build args if needed, but for now assume no)
RUN npm run build

# Use nginx to serve
FROM nginx:alpine

# Copy built app
COPY --from=build /app/dist /usr/share/nginx/html

# Copy nginx config if needed, but default is fine for SPA
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
