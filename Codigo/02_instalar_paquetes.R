# Instala renv en una biblioteca del usuario y restaura las versiones de renv.lock.
# Uso: Rscript --vanilla 02_instalar_paquetes.R ruta_al_proyecto
args <- commandArgs(trailingOnly = TRUE)
project <- if (length(args)) normalizePath(args[1], mustWork = TRUE) else getwd()
# Este bloqueo se generó y validó con R 4.5.0; R 4.6 retiró interfaces que
# utilizan varias versiones archivadas. Se rechaza antes de instalar paquetes.
version_requerida <- "4.5.0"
if (as.character(getRversion()) != version_requerida)
  stop(paste("R incompatible:", getRversion(), "; este renv.lock requiere R", version_requerida,
             ". Seleccionar su Rscript con --rscript o RSCRIPT."))
options(repos = c(CRAN = "https://cloud.r-project.org"), timeout = 600)
Sys.setenv(RENV_CONFIG_CONSENT = "TRUE", RENV_CONFIG_AUTO_SNAPSHOT = "FALSE")

# El arranque no requiere permisos de administrador ni modificar la instalación de R.
bootstrap <- file.path(project, "renv", "bootstrap", paste0("R-", getRversion()))
dir.create(bootstrap, recursive = TRUE, showWarnings = FALSE)
.libPaths(c(bootstrap, .libPaths()))
if (!requireNamespace("renv", quietly = TRUE) || as.character(packageVersion("renv")) != "1.3.1") {
  # Se intenta el repositorio vigente; si la versión fue archivada, se usa CRAN Archive.
  archivo <- tempfile(fileext = ".tar.gz")
  urls <- c("https://cloud.r-project.org/src/contrib/renv_1.3.1.tar.gz",
            "https://cloud.r-project.org/src/contrib/Archive/renv/renv_1.3.1.tar.gz")
  descargado <- FALSE
  for (u in urls) {
    intento <- try(utils::download.file(u, archivo, mode = "wb", quiet = TRUE), silent = TRUE)
    if (!inherits(intento, "try-error") && intento == 0L) { descargado <- TRUE; break }
  }
  if (!descargado) stop("No se pudo descargar renv 1.3.1 desde CRAN.")
  utils::install.packages(archivo, lib = bootstrap, repos = NULL, type = "source")
}

# El archivo de bloqueo incluye calidad 0.8.2, survey y sus dependencias transitivas.
# renv elegirá binarios cuando estén disponibles; algunas versiones archivadas
# pueden requerir herramientas de compilación de R en el equipo de ejecución.
stopifnot(file.exists(file.path(project, "renv.lock")))
target <- renv::paths$library(project = project)
dir.create(target, recursive = TRUE, showWarnings = FALSE)
renv::restore(project = project, library = target,
              lockfile = file.path(project, "renv.lock"), prompt = FALSE)
renv::load(project = project)
stopifnot(as.character(packageVersion("calidad")) == "0.8.2")
print(data.frame(paquete = c("R", "renv", "calidad", "survey"),
                 version = c(as.character(getRversion()), as.character(packageVersion("renv")),
                             as.character(packageVersion("calidad")), as.character(packageVersion("survey")))))
