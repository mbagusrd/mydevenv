<?php
header('Content-Type: text/html; charset=utf-8');
?>
<!DOCTYPE html>
<html>
<head>
    <title>Demo Project - MyDevEnv Portable Stack</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #f8fafc; color: #1e293b; padding: 40px; }
        .card { max-width: 650px; margin: 0 auto; background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
        h1 { font-size: 20px; color: #0284c7; margin-top: 0; }
        table { width: 100%; border-collapse: collapse; margin-top: 16px; font-size: 14px; }
        td { padding: 8px 12px; border-bottom: 1px solid #f1f5f9; }
        td.label { font-weight: 600; width: 40%; color: #64748b; }
        .tag { background: #e0f2fe; color: #0369a1; padding: 2px 8px; border-radius: 4px; font-weight: bold; }
    </style>
</head>
<body>
    <div class="card">
        <h1>MyDevEnv Portable Stack Active</h1>
        <p>Project demo berhasil diakses via web server.</p>
        <table>
            <tr>
                <td class="label">Versi PHP Aktif</td>
                <td><span class="tag">PHP <?= phpversion(); ?></span></td>
            </tr>
            <tr>
                <td class="label">Host Domain</td>
                <td><?= htmlspecialchars(isset($_SERVER['HTTP_HOST']) ? $_SERVER['HTTP_HOST'] : '-'); ?></td>
            </tr>
            <tr>
                <td class="label">Document Root</td>
                <td><?= htmlspecialchars(isset($_SERVER['DOCUMENT_ROOT']) ? $_SERVER['DOCUMENT_ROOT'] : '-'); ?></td>
            </tr>
            <tr>
                <td class="label">Server Software</td>
                <td><?= htmlspecialchars(isset($_SERVER['SERVER_SOFTWARE']) ? $_SERVER['SERVER_SOFTWARE'] : '-'); ?></td>
            </tr>
        </table>
    </div>
</body>
</html>
