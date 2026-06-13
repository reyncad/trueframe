using Microsoft.AspNetCore.DataProtection;
using TrueFrameUI.Services;

var builder = WebApplication.CreateBuilder(args);

// ── Servisler ─────────────────────────────────────────────────
builder.Services.AddControllersWithViews(options =>
{
    // Global CSRF filtresi — tüm POST action'larında otomatik doğrulama
    options.Filters.Add(new Microsoft.AspNetCore.Mvc.AutoValidateAntiforgeryTokenAttribute());
});

builder.Services.AddHttpContextAccessor();
builder.Services.AddHttpClient();
builder.Services.AddSingleton<UserStore>();
builder.Services.AddScoped<TranslationService>();

// ── DataProtection ────────────────────────────────────────────
// Key'leri kalıcı bir dizine yaz; container yeniden oluşturulduğunda
// session ve antiforgery token'lar geçerliliğini korur.
// Docker: /app/DataProtection-Keys → frontend_keys volume'una mount edilir.
var dpKeysPath = builder.Configuration["DataProtectionKeysPath"]
    ?? Path.Combine(builder.Environment.ContentRootPath, "DataProtection-Keys");
Directory.CreateDirectory(dpKeysPath);
builder.Services.AddDataProtection()
    .PersistKeysToFileSystem(new DirectoryInfo(dpKeysPath))
    .SetApplicationName("TrueFrame");
// NOT: "No XML encryptor configured" uyarısı beklenen bir davranış —
// key'ler şifresiz dosyaya yazılıyor. Bu geliştirme ortamında kabul edilebilir.
// Production'da: .ProtectKeysWithCertificate(cert) veya Azure Key Vault eklenebilir.

// ── Session ───────────────────────────────────────────────────
builder.Services.AddSession(options =>
{
    options.IdleTimeout     = TimeSpan.FromMinutes(60);
    options.Cookie.Name     = "__TF_Session";
    options.Cookie.HttpOnly = true;   // JavaScript'in cookie'ye erişimini engelle
    options.Cookie.SecurePolicy = builder.Environment.IsDevelopment()
        ? Microsoft.AspNetCore.Http.CookieSecurePolicy.None
        : Microsoft.AspNetCore.Http.CookieSecurePolicy.Always;  // Production'da HTTPS zorunlu
    options.Cookie.SameSite = Microsoft.AspNetCore.Http.SameSiteMode.Strict;  // CSRF koruması
});

// ── Antiforgery ───────────────────────────────────────────────
builder.Services.AddAntiforgery(options =>
{
    options.Cookie.Name     = "__TF_CSRF";
    options.Cookie.HttpOnly = true;
    options.Cookie.SecurePolicy = builder.Environment.IsDevelopment()
        ? Microsoft.AspNetCore.Http.CookieSecurePolicy.None
        : Microsoft.AspNetCore.Http.CookieSecurePolicy.Always;
});

var app = builder.Build();

// ── HTTP Pipeline ─────────────────────────────────────────────
if (!app.Environment.IsDevelopment())
{
    app.UseExceptionHandler("/Home/Error");
    app.UseHsts();
}

app.UseHttpsRedirection();
app.UseStaticFiles();
app.UseRouting();

// Session UseRouting'den sonra, UseAuthorization'dan önce gelmelidir
app.UseSession();
app.UseAuthorization();

// ── Güvenlik Headers ──────────────────────────────────────────
app.Use(async (context, next) =>
{
    context.Response.Headers["X-Content-Type-Options"] = "nosniff";
    context.Response.Headers["X-Frame-Options"]        = "DENY";
    context.Response.Headers["X-XSS-Protection"]       = "1; mode=block";
    context.Response.Headers["Referrer-Policy"]        = "same-origin";
    await next();
});

app.MapControllerRoute(
    name: "default",
    pattern: "{controller=Home}/{action=Index}/{id?}");

app.Run();
