# ege.physdb.ru

The exam site runs beside the existing `physdb.ru` service on the same VDS.
It reads the versioned SQLite database and source files from
`/var/www/phys-ege`; it listens only on `127.0.0.1:8002`.

1. Add an `A` record for `ege.physdb.ru` pointing to the VDS address.
2. Clone this public repository to `/var/www/phys-ege`.
   Install the PDF engine: `apt-get install --no-install-recommends texlive-xetex texlive-lang-cyrillic fonts-liberation`.
3. Install `deploy/phys-ege.service` as `/etc/systemd/system/phys-ege.service`
   and `deploy/nginx-phys-ege.conf` as
   `/etc/nginx/sites-available/phys-ege`; link it from `sites-enabled`.
4. Run `systemctl daemon-reload`, enable/start `phys-ege.service`, check
   `nginx -t`, and reload nginx. Check `/api/health` through nginx.
5. After DNS resolves, run
   `certbot --nginx -d ege.physdb.ru --redirect --non-interactive --agree-tos`
   using the existing Certbot account. Check HTTPS and automatic renewal.

For updates, run `git pull --ff-only` in `/var/www/phys-ege`, then restart
`phys-ege.service` and check `/api/health`. The existing `physics-db.service`
and nginx host are independent.
