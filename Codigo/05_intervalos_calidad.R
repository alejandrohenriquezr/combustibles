# Gasto mediano / ingreso mediano de los MISMOS hogares gastadores.
# Uso: Rscript --vanilla 05_intervalos_calidad.R hogares.csv salida
args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 2L) stop("Se requieren hogares.csv y carpeta de salida.")
# El cálculo directo también conserva el R de referencia de renv.lock.
if (as.character(getRversion()) != "4.5.0") stop("Este análisis requiere R 4.5.0, según renv.lock.")
lib <- Sys.getenv("EPF_R_LIB"); if (nzchar(lib)) .libPaths(c(lib, .libPaths()))
for (p in c("survey", "calidad")) if (!requireNamespace(p, quietly=TRUE)) stop(paste("Falta",p,"; ejecutar 01_instalar_dependencias.py"))
stopifnot(as.character(utils::packageVersion("calidad")) == "0.8.2")
options(survey.lonely.psu="fail", survey.adjust.domain.lonely=FALSE)
out <- args[2]; dir.create(out, recursive=TRUE, showWarnings=FALSE)
# Python exporta UTF-8 con BOM para Excel. En Windows, sin codificación explícita,
# R incorpora el BOM al primer nombre y transforma "fe" en "X...fe".
h <- read.csv(args[1], fileEncoding="UTF-8-BOM",
              colClasses=c(folio="character",estrato_muestreo="character",var_unit="character"))
stopifnot(!anyDuplicated(h$folio), all(h$fe > 0))
h$varstrat <- h$estrato_muestreo; h$varunit <- h$var_unit
dc <- survey::svydesign(ids=~varunit,strata=~varstrat,weights=~fe,data=h,nest=TRUE)

# Control nativo de calidad contra la tabla 5 del manual, p. 82.
control <- calidad::create_mean("ing_disp_hog_hd",design=dc,ci=TRUE)
stopifnot(abs(control$se-18082.39)<.02, control$df==3320)
write.csv(control,file.path(out,"control_calidad.csv"),row.names=FALSE)

# Los grupos se forman antes del filtro. Se conservan factores fraccionarios.
# El ingreso <=0 NO se excluye: ambas medianas usan todos los hogares con gasto.
grupos <- list(list(tipo="Total",grupo="Total",fr=rep(1,nrow(h))))
for (q in 1:5) grupos[[length(grupos)+1L]] <- list(tipo="Quintil",grupo=as.character(q),
  fr=h[[paste0("fraccion_decil_",2*q-1)]]+h[[paste0("fraccion_decil_",2*q)]])
for (q in 1:10) grupos[[length(grupos)+1L]] <- list(tipo="Decil",grupo=as.character(q),fr=h[[paste0("fraccion_decil_",q)]])
dominios <- list()
for (g in grupos) for (fuel in c("gasolina_diesel","gasolina","diesel")) {
  ix <- which(g$fr>1e-12 & h[[fuel]]>0)
  if (!length(ix)) stop("Dominio sin hogares gastadores: no se presume mediana cero.")
  d <- dc[ix, ]; gl <- min(1998L,survey::degf(d))
  dominios[[length(dominios)+1L]] <- list(tipo=g$tipo,grupo=g$grupo,fuel=fuel,fr=g$fr,
    ix_g=ix[order(h[[fuel]][ix],method="radix")],
    ix_y=ix[order(h$ing_disp_hog_hd[ix],method="radix")],
    n=length(ix),n_todos=sum(g$fr>1e-12),gl=gl,
    peso=sum(h$fe[ix]*g$fr[ix]),peso_todos=sum(h$fe*g$fr),
    n_ingreso_no_positivo=sum(h$ing_disp_hog_hd[ix]<=0))
}

# Se remuestrean pseudo-conglomerados dentro de estratos sobre el diseño completo.
# Es una aproximación con datos públicos; cortes y factores finales permanecen fijos
# y no se reproduce la calibración ni el ajuste de no respuesta en cada réplica.
B <- 1999L; semilla <- 20261119L
RNGkind("Mersenne-Twister","Inversion","Rejection"); set.seed(semilla)
boot <- survey::bootweights(h$varstrat,h$varunit,replicates=B,compress=TRUE)
rd <- survey::svrepdesign(data=h,weights=~fe,repweights=boot$repweights,type="bootstrap",
  combined.weights=FALSE,scale=boot$scale,rscales=boot$rscales,mse=TRUE,degf=min(B-1L,survey::degf(dc)))
tipos <- c("gasto_mediano","ingreso_mediano","relacion_medianas")
etiquetas <- unlist(lapply(dominios,function(d) paste(d$tipo,d$grupo,d$fuel,tipos,sep="_")))
theta <- function(w,data) {
  v <- numeric(length(dominios)*3L)
  for (i in seq_along(dominios)) {
    d <- dominios[[i]]
    # Cuantil empírico ponderado: primer valor que alcanza el 50%, sin interpolar.
    med <- function(ix,valores) {
      acumulado <- cumsum(w[ix]*d$fr[ix]); total <- tail(acumulado,1)
      if (total<=0) stop("Réplica sin peso en un dominio.")
      valores[ix[which(acumulado>=.5*total)[1]]]
    }
    gasto <- med(d$ix_g,h[[d$fuel]]); ingreso <- med(d$ix_y,h$ing_disp_hog_hd)
    if (ingreso<=0) stop("Ingreso mediano no positivo; la relación no se puede interpretar.")
    v[3L*i+c(-2L,-1L,0L)] <- c(gasto,ingreso,gasto/ingreso)
  }
  names(v) <- etiquetas; v
}
rep <- survey::withReplicates(rd,theta,return.replicates=TRUE)
estimados <- as.numeric(rep$theta); V <- as.matrix(attr(rep$theta,"var")); ee <- sqrt(diag(V))
R <- as.matrix(rep$replicates)
stopifnot(nrow(R)==B,ncol(R)==length(estimados),all(is.finite(R)))
ic <- apply(R,2,stats::quantile,probs=c(.025,.975),type=1,names=FALSE)

# calidad no tiene un estimador nativo de razón de medianas. Se entrega a assess
# la estructura de insumos de su clase de medias/razones para aplicar sus criterios
# n, gl y CV. Es una adaptación explícita; los IC provienen del bootstrap conjunto,
# y no de create_prop ni de dividir los extremos de intervalos de las dos medianas.
evaluar <- function(stat,se,n,gl,razon) {
  if (se==0) return("Sin clasificación: EE bootstrap nulo")
  tab <- data.frame(stat=stat,se=se,n=n,df=gl,cv=se/abs(stat))
  class(tab) <- c(if (razon) "calidad.prop" else "calidad.mean","data.frame")
  eva <- calidad::assess(tab,scheme="chile",ratio_between_0_1=FALSE)
  stopifnot(nrow(eva)==1L,!is.na(eva$label))
  c(reliable="Fiable",`weakly reliable`="Poco fiable",`non-reliable`="No fiable")[[eva$label]]
}
precision <- list(); resumen <- list(); k <- 0L
for (i in seq_along(dominios)) {
  d <- dominios[[i]]; ids <- 3L*i+c(-2L,-1L,0L)
  r <- data.frame(segmentacion=d$tipo,grupo=d$grupo,combustible=d$fuel,
    n_gastadores=d$n,n_todos=d$n_todos,peso_gastadores=d$peso,peso_todos=d$peso_todos,
    participacion=d$peso/d$peso_todos,n_ingreso_no_positivo=d$n_ingreso_no_positivo,
    gasto_mediano=estimados[ids[1]],ingreso_mediano=estimados[ids[2]],relacion_medianas=estimados[ids[3]])
  for (j in 1:3) {
    id <- ids[j]; cal <- evaluar(estimados[id],ee[id],d$n,d$gl,j==3L)
    k <- k+1L; precision[[k]] <- data.frame(segmentacion=d$tipo,grupo=d$grupo,combustible=d$fuel,
      indicador=tipos[j],estimacion=estimados[id],ee=ee[id],li95=ic[1,id],ls95=ic[2,id],
      cv=ee[id]/abs(estimados[id]),n=d$n,gl=d$gl,clasificacion=cal,
      metodo="IC percentil bootstrap conjunto, 1999 réplicas, tipo=1",
      evaluacion="Criterios n/gl/CV de calidad, adaptación a medianas y razón de medianas")
    r[[paste0(tipos[j],"_li95")]] <- ic[1,id];r[[paste0(tipos[j],"_ls95")]] <- ic[2,id]
    r[[paste0(tipos[j],"_calidad")]] <- cal
  }
  resumen[[i]] <- r
}

# Contrastes de quintiles adyacentes, dentro de cada indicador, usando la covarianza
# del mismo bootstrap. La familia gráfica tiene cuatro comparaciones de Holm.
contrastes <- list(); covs <- list(); k <- 0L; l <- 0L
qids <- which(vapply(dominios,function(d)d$tipo=="Quintil" && d$fuel=="gasolina_diesel",logical(1)))
stopifnot(length(qids)==5L)
for (j in 1:3) {
  ids <- 3L*qids+j-3L; vv <- V[ids,ids]; pts <- estimados[ids]
  for (a in 1:5) for (b in 1:5) {
    l<-l+1L;covs[[l]]<-data.frame(indicador=tipos[j],grupo_a=a,grupo_b=b,covarianza=vv[a,b])
  }
  pares <- t(utils::combn(1:5,2)); filas <- list()
  for (i in seq_len(nrow(pares))) {
    a<-pares[i,1];b<-pares[i,2];da<-dominios[[qids[a]]];db<-dominios[[qids[b]]]
    ix<-which(h$gasolina_diesel>0 & (da$fr>1e-12 | db$fr>1e-12));gl<-min(B-1L,survey::degf(dc[ix,]))
    dif<-pts[b]-pts[a];sed<-sqrt(max(0,vv[a,a]+vv[b,b]-2*vv[a,b]))
    if (sed<=0) stop("Contraste sin variación; no asignar una marca de significancia.")
    filas[[i]]<-data.frame(indicador=tipos[j],grupo_a=a,grupo_b=b,estimacion_a=pts[a],estimacion_b=pts[b],
      diferencia_b_a=dif,ee_diferencia=sed,covarianza=vv[a,b],gl=gl,
      p_sin_ajuste=2*stats::pt(-abs(dif/sed),df=gl),adyacente=b==a+1L,
      metodo="Wald t, covarianza del bootstrap conjunto de 1999 réplicas")
  }
  t<-do.call(rbind,filas);t$p_holm_10<-stats::p.adjust(t$p_sin_ajuste,method="holm")
  t$p_holm_adyacentes<-NA_real_;t$p_holm_adyacentes[t$adyacente]<-stats::p.adjust(t$p_sin_ajuste[t$adyacente],method="holm")
  t$marca_grafico<-ifelse(t$adyacente & !is.na(t$p_holm_adyacentes) & t$p_holm_adyacentes>=.05,"†","")
  k<-k+1L;contrastes[[k]]<-t
}
write.csv(do.call(rbind,resumen),file.path(out,"medianas_resumen.csv"),row.names=FALSE,fileEncoding="UTF-8")
write.csv(do.call(rbind,precision),file.path(out,"medianas_precision.csv"),row.names=FALSE,fileEncoding="UTF-8")
write.csv(do.call(rbind,contrastes),file.path(out,"contrastes.csv"),row.names=FALSE,na="",fileEncoding="UTF-8")
write.csv(do.call(rbind,covs),file.path(out,"covarianzas.csv"),row.names=FALSE)
colnames(R)<-etiquetas;write.csv(R,file.path(out,"replicas_medianas.csv"),row.names=FALSE)
write.csv(data.frame(replicas=B,semilla=semilla,metodo="bootstrap de PSU dentro de estratos; factores y cortes fijos"),file.path(out,"metodo_contrastes.csv"),row.names=FALSE)
write.csv(data.frame(paquete=c("R","calidad","survey"),version=c(as.character(getRversion()),as.character(utils::packageVersion("calidad")),as.character(utils::packageVersion("survey")))),file.path(out,"versiones_R.csv"),row.names=FALSE)
capture.output(sessionInfo(),file=file.path(out,"sessionInfo_R.txt"))
message("Razón de medianas: 48 dominios, 144 estimaciones con IC, 30 contrastes; ingreso <=0 conservado.")

# Curva GPP: cambio del gasto MEDIANO revalorado / ingreso MEDIANO del mismo
# conjunto gastador. Se conserva así la métrica del artículo. Es un escenario
# con cantidades/mezcla e ingresos EPF de referencia, no gasto observado actual.
script_arg <- grep("^--file=",commandArgs(),value=TRUE)
raiz <- dirname(normalizePath(sub("^--file=","",script_arg[1])))
precios <- read.csv(file.path(raiz,"gpp_chile_clp.csv"),stringsAsFactors=FALSE)
stopifnot(!anyDuplicated(precios$mes),all(precios$gasolina_clp>0),all(precios$diesel_clp>0))
M <- nrow(precios);fg <- precios$gasolina_clp/precios$gasolina_clp[1]
fd <- precios$diesel_clp/precios$diesel_clp[1]
esc <- lapply(qids,function(i) {
  d <- dominios[[i]];ix <- d$ix_g
  valores <- lapply(seq_len(M),function(t) h$gasolina*fg[t]+h$diesel*fd[t])
  ordenes <- lapply(valores,function(v)ix[order(v[ix],method="radix")])
  list(d=d,valores=valores,ordenes=ordenes)
})
theta_esc <- function(w,data) {
  salida <- numeric(5L*M)
  for (q in 1:5) {
    e<-esc[[q]];d<-e$d
    med <- function(ix,v) {
      z<-cumsum(w[ix]*d$fr[ix]);total<-tail(z,1)
      if(total<=0)stop("Réplica GPP sin peso en un quintil.")
      v[ix[which(z>=.5*total)[1]]]
    }
    ingreso<-med(d$ix_y,h$ing_disp_hog_hd);base<-med(d$ix_g,h$gasolina_diesel)
    if(ingreso<=0)stop("Ingreso mediano no positivo en curva GPP.")
    for(t in seq_len(M))salida[(q-1L)*M+t]<-if(t==1L)0 else (med(e$ordenes[[t]],e$valores[[t]])-base)/ingreso
  }
  names(salida)<-unlist(lapply(1:5,function(q)paste0("Q",q,"_",precios$mes)))
  salida
}
# Se reutilizan los MISMOS ponderadores bootstrap de PSU del análisis EPF.
re<-survey::withReplicates(rd,theta_esc,return.replicates=TRUE)
ve<-as.numeric(re$theta);VV<-as.matrix(attr(re$theta,"var"));SE<-sqrt(diag(VV))
RR<-as.matrix(re$replicates);IC<-apply(RR,2,stats::quantile,probs=c(.025,.975),type=1,names=FALSE)
filas<-list();tests<-list();k<-0L
for(t in seq_len(M)) {
  ids<-(0:4)*M+t;v<-ve[ids];vv<-VV[ids,ids];tt<-list()
  for(q in 2:5) {
    sed<-sqrt(max(0,vv[q,q]+vv[q-1,q-1]-2*vv[q,q-1]))
    ix<-which(h$gasolina_diesel>0 & (esc[[q]]$d$fr>1e-12|esc[[q-1]]$d$fr>1e-12))
    gl<-min(B-1L,survey::degf(dc[ix,]))
    pp<-if(t==1L)NA_real_ else if(sed>0)2*stats::pt(-abs((v[q]-v[q-1])/sed),df=gl) else NA_real_
    tt[[q-1L]]<-data.frame(mes=precios$mes[t],grupo_a=q-1,grupo_b=q,diferencia=v[q]-v[q-1],
        ee_diferencia=sed,covarianza=vv[q,q-1],gl=gl,p_sin_ajuste=pp)
  }
  tt<-do.call(rbind,tt);tt$p_holm<-stats::p.adjust(tt$p_sin_ajuste,method="holm")
  tt$marca<-ifelse(!is.na(tt$p_holm)&tt$p_holm>=.05,"○","")
  tests[[t]]<-tt
  for(q in 1:5) {
    i<-ids[q];d<-esc[[q]]$d
    cal<-if(t==1L)"Base cero; no aplica" else evaluar(ve[i],SE[i],d$n,d$gl,FALSE)
    # El cero de referencia es una identidad, no una estimación de precisión perfecta.
    k<-k+1L;filas[[k]]<-data.frame(mes=precios$mes[t],quintil=q,
      gasolina_clp=precios$gasolina_clp[t],diesel_clp=precios$diesel_clp[t],
      indice_gasolina=fg[t],indice_diesel=fd[t],estimacion=ve[i],ee=SE[i],
      li95=IC[1,i],ls95=IC[2,i],cv=if(ve[i]==0)NA_real_ else SE[i]/abs(ve[i]),
      n=d$n,gl=d$gl,clasificacion=cal,
      marca_no_significativa=if(q==1L)"" else tt$marca[q-1L],
      marca_no_fiable=if(cal=="No fiable")"×" else "")
  }
}
write.csv(do.call(rbind,filas),file.path(out,"escenario_gpp_ic.csv"),row.names=FALSE,na="",fileEncoding="UTF-8")
write.csv(do.call(rbind,tests),file.path(out,"escenario_gpp_contrastes.csv"),row.names=FALSE,na="",fileEncoding="UTF-8")
write.csv(RR,file.path(out,"replicas_escenario_gpp.csv"),row.names=FALSE)
message("Curva GPP: ",M," meses, cinco quintiles; IC y contrastes conjuntos condicionados a precios publicados.")
