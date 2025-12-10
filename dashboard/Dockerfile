# dashboard/Dockerfile
FROM node:18-alpine

WORKDIR /app

# Copy package.json first to leverage Docker cache
COPY package.json .

# Install dependencies during the build process
RUN npm install

# Copy the rest of the application code
COPY . .

# Default command
CMD ["npm", "start"]
