# One-time extraction: real CTRPv2 sensitivity data (aac_recomputed) into a
# plain CSV, since the source .rds is a PharmacoGx PharmacoSet (S4 object)
# that Python's pyreadr cannot parse. Base R's own readRDS() + attr() CAN
# read it directly without the PharmacoGx package installed at all (S4
# slot values are still accessible generically) -- see
# synlethality/ingest/ctrp.py's docstring for the full story of how this
# was found. This script is the one real place R is used in this project;
# everything downstream (name mapping, aggregation, DB loading) is plain
# Python, matching every other ingestion step.
args <- commandArgs(trailingOnly = TRUE)
rds_path <- args[1]
out_path <- args[2]

obj <- readRDS(rds_path)
sens <- attr(obj, "sensitivity")
info <- sens$info
profiles <- sens$profiles

out <- data.frame(
  cellid = info$cellid,
  drugid = info$drugid,
  culture_media = info$culture_media,
  aac_recomputed = profiles$aac_recomputed
)
out <- out[!is.na(out$aac_recomputed), ]
write.csv(out, out_path, row.names = FALSE)
cat("Wrote", nrow(out), "real non-NA experiment rows to", out_path, "\n")
