# Verificación de solo lectura: no instala, actualiza ni compila paquetes.
# Uso: Rscript --vanilla 12_verificar_entorno.R ruta_del_proyecto
args <- commandArgs(trailingOnly = TRUE)
project <- normalizePath(if (length(args)) args[1] else getwd(), winslash = "/", mustWork = TRUE)

# Cada etapa se escribe antes de ejecutarse, para conservar el punto de fallo.
etapa <- function(texto) {
  cat("EPF_ETAPA_R=", texto, "\n", sep = "")
  flush(stdout())
}
etapa(paste("R", getRversion(), "; biblioteca de arranque"))
bootstrap <- file.path(project, "renv", "bootstrap", paste0("R-", getRversion()))
.libPaths(c(bootstrap, .libPaths()))
if (!requireNamespace("renv", quietly = TRUE))
  stop("Falta renv; ejecutar 01_instalar_dependencias.py --solo-r.")

# renv lee su bloqueo con su propio lector; no se depende de jsonlite para arrancar.
etapa("Leer renv.lock")
bloqueo <- renv::lockfile_read(file.path(project, "renv.lock"))
if (as.character(getRversion()) != bloqueo$R$Version)
  stop(paste("R incompatible:", getRversion(), "; renv.lock requiere", bloqueo$R$Version))
biblioteca <- renv::paths$library(project = project)
if (!dir.exists(biblioteca))
  stop(paste("No existe la biblioteca del proyecto:", biblioteca))

# Se usan la biblioteca del proyecto, su arranque y los paquetes de ESTE R.
# Se excluyen bibliotecas de usuario o de sitio ajenas al proyecto.
.libPaths(c(biblioteca, bootstrap, .Library), include.site = FALSE)
etapa("Comprobar versiones instaladas")
ip <- utils::installed.packages(lib.loc = c(biblioteca, bootstrap, .Library))
nombres <- names(bloqueo$Packages)
versiones <- vapply(bloqueo$Packages, function(p) p$Version, character(1))
actual <- ip[match(nombres, ip[, "Package"]), "Version"]

# compareVersion trata 4.4-2 y 4.4.2 como la misma versión numérica de R.
correcta <- vapply(seq_along(nombres), function(i) {
  !is.na(actual[i]) && utils::compareVersion(actual[i], versiones[i]) == 0L
}, logical(1))
if (any(!correcta)) {
  detalle <- paste0(nombres[!correcta], " [instalada=", actual[!correcta],
                    "; requerida=", versiones[!correcta], "]")
  stop(paste("Paquetes pendientes:", paste(detalle, collapse = ", "),
             "; ejecutar 01_instalar_dependencias.py --solo-r."))
}

# La instalación registrada no basta: se comprueba la carga real de ambos paquetes.
for (p in c("survey", "calidad")) {
  etapa(paste("Cargar", p))
  tryCatch(loadNamespace(p), error = function(e)
    stop(paste("No se pudo cargar", p, ":", conditionMessage(e)), call. = FALSE))
}
etapa("Verificación terminada")
cat("EPF_R_LIB=", normalizePath(biblioteca, winslash = "/", mustWork = TRUE), "\n", sep = "")
