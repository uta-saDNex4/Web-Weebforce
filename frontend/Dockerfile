FROM node:20-alpine AS builder

WORKDIR /app

COPY frontend/package*.json ./
RUN npm install

COPY frontend/ ./
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production

COPY frontend/package*.json ./
RUN npm install --omit=dev

COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/src ./src

EXPOSE 3000

CMD ["npm", "run", "start"]
