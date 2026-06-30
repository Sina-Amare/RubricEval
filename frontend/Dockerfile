FROM node:22-alpine

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# The API URL is inlined into the client bundle at build time (Next.js bakes
# NEXT_PUBLIC_* during `next build`), so it must be set here, not just at runtime.
ARG NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL
RUN npm run build

EXPOSE 3000
CMD ["npm", "run", "start"]
