# Use an official Node.js runtime as base
FROM node:20-alpine

# Set working directory inside container
WORKDIR /app

# Install dependencies first (for better caching)
COPY package*.json ./

RUN npm ci

# Copy the rest of your app
COPY . .

# Compile TypeScript
RUN npx tsc main.ts --target es2020 --module commonjs --esModuleInterop --resolveJsonModule --outDir .

# Set default port for the application
ENV PORT=9001

# Expose the port your app runs on
EXPOSE 9001

# Start the app directly with node
CMD ["node", "main.js"]
