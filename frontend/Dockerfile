FROM node:24-bookworm-slim

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install

COPY index.html vite.config.ts tsconfig*.json eslint.config.js ./
COPY public ./public
COPY src ./src

EXPOSE 5173

CMD ["npm", "run", "dev"]
