# ==========================================================================
#  Frontend REVISIO — build multi-étapes.
#  1. deps    : installe node_modules (mis en cache tant que package.json ne
#               change pas).
#  2. build   : compile Next.js en mode standalone.
#  3. runtime : ne contient que le serveur compilé — ni sources, ni devDeps.
# ==========================================================================

FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
# `npm ci` si un lockfile existe (reproductible), sinon `npm install`.
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

FROM node:22-alpine AS build
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# Les variables NEXT_PUBLIC_* sont figées AU BUILD dans le bundle JS :
# les changer ensuite exige de reconstruire l'image.
ARG NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:22-alpine AS runtime
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

COPY --from=build /app/public ./public
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static

EXPOSE 3000
CMD ["node", "server.js"]
