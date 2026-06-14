# ─────────────────────────────────────────────────────────────
# TrueFrame Frontend — ASP.NET Core MVC
# Çok aşamalı build: SDK ile derle, runtime ile çalıştır.
# ─────────────────────────────────────────────────────────────

# Aşama 1: Build
FROM mcr.microsoft.com/dotnet/sdk:10.0 AS build
WORKDIR /src

# .csproj kopyala ve restore (layer cache)
COPY TrueFrameUI.csproj .
RUN dotnet restore

# Kaynak kodun tamamını kopyala ve yayımla
COPY . .
RUN dotnet publish -c Release -o /app/publish 

# Aşama 2: Runtime
FROM mcr.microsoft.com/dotnet/aspnet:10.0 AS runtime
WORKDIR /app

# Yüklenen görseller için uploads dizini (volume olarak mount edilebilir)
RUN groupadd --system appgroup && useradd --system --gid appgroup appuser

COPY --from=build /app/publish .

# Dizinleri oluştur ve sahipliği appuser'a ver (COPY sonrası yapılmalı)
# DataProtection-Keys: volume mount edilse bile dizin zaten appuser'a ait olur,
# böylece "Permission denied" hatası oluşmaz.
RUN mkdir -p /app/wwwroot/uploads /app/Data /app/DataProtection-Keys && \
    chown -R appuser:appgroup /app

USER appuser

EXPOSE 8080

ENV ASPNETCORE_URLS=http://+:8080
ENV ASPNETCORE_ENVIRONMENT=Production

ENTRYPOINT ["dotnet", "TrueFrameUI.dll"]
