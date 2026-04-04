FROM node:20-alpine AS builder

WORKDIR /app
COPY webapp/package.json webapp/package-lock.json ./
RUN npm ci --ignore-scripts
COPY webapp/ ./
ENV NEXT_PUBLIC_API_URL=http://14.225.207.145:8100
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

EXPOSE 3003
CMD ["node", "server.js"]
