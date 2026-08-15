# Build Stage
FROM golang:1.26-alpine AS builder
WORKDIR /app
COPY go.mod ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -o ingress-service .

# Production Stage (Ultra-small runtime container ~15MB)
FROM alpine:latest
RUN apk --no-cache add ca-certificates
WORKDIR /root/
COPY --from=builder /app/ingress-service .
EXPOSE 8080
ENV PORT=8080
CMD ["./ingress-service"]