FROM node:22-slim
WORKDIR /app
RUN corepack enable && corepack prepare pnpm@latest --activate
COPY package.json pnpm-workspace.yaml ./
COPY packages/protocol/package.json packages/protocol/
COPY packages/server/package.json packages/server/
COPY packages/client/package.json packages/client/
RUN pnpm install
COPY . .
RUN pnpm --filter @weather/protocol build \
 && pnpm --filter @weather/client build \
 && pnpm --filter @weather/server build
CMD ["node", "packages/server/dist/index.js"]
