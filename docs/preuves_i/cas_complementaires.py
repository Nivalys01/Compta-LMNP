import json
import reproduire as a
out={}
for fees in (False,True):
 c,p=a.new(n=2);a.addcomp(c,1,10000);a.addcomp(c,2,30000)
 for b,amt in ((1,2000 if fees else 500),(2,1000)):
  a.operations.saisir(c,type='loyer',montant=amt,date_operation='2026-01-10',bien_id=b)
 if fees:a.operations.saisir(c,type='honoraires',montant=1500,date_operation='2026-01-10',bien_id=1)
 a.cession.ceder_bien(c,1,'2026-12-31',10000)
 r=a.fiscal.cloturer(c,2026)
 out['honoraires' if fees else 'cle_marges']={'suivi':r['suivi_39c'],'biens':a.fiscal.suivi_39c_par_bien(c,2026),'controles':[x.code for x in a.controles.controler(c,2026)]}
 c.close()
from pathlib import Path
Path(__file__).with_name('cas_complementaires.json').write_text(json.dumps(out,indent=2))
print(json.dumps(out))
