FROM node:22.13.0-bookworm-slim AS build
WORKDIR /app
COPY showcase/package.json showcase/package-lock.json ./
RUN npm ci
COPY showcase/ ./
RUN npm run build

FROM node:22.13.0-bookworm-slim AS runtime
WORKDIR /app
ENV NODE_ENV=production
COPY --from=build /app /app
EXPOSE 3000
CMD ["npm", "run", "start", "--", "--host", "0.0.0.0"]
