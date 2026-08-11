/* Minimum JavaScriptu — reszta narzędzia działa na zwykłych formularzach.
   Powód jest praktyczny: formularz przeżywa odświeżenie strony, przycisk
   wstecz i wklejony adres, a stan trzymany w przeglądarce nie przeżywa
   niczego z tych trzech. */

function toast(tekst, blad) {
  var t = document.getElementById('toast');
  if (!t) return;
  t.textContent = tekst;
  t.className = 'toast show' + (blad ? ' err' : '');
  clearTimeout(toast._t);
  toast._t = setTimeout(function () { t.className = 'toast'; }, 2600);
}

/* Przełącznik „objęta działaniem” na karcie placówki. Zapis leci od razu —
   bez przycisku „zapisz”, bo to jedno pole i nie ma czego zatwierdzać. */
document.addEventListener('change', function (e) {
  var el = e.target;
  if (el.id !== 'objeta') return;
  fetch('/api/objeta', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ rspo: Number(el.dataset.rspo), wartosc: el.checked })
  }).then(function (r) { return r.json(); })
    .then(function (d) {
      if (d.ok) toast(el.checked ? 'Oznaczono jako objętą działaniem'
                                 : 'Zdjęto oznaczenie');
      else { el.checked = !el.checked; toast(d.blad || 'Nie zapisano', true); }
    })
    .catch(function () { el.checked = !el.checked; toast('Brak połączenia', true); });
});

/* Wgrywanie pliku: 42 MB idzie kilkanaście sekund, a przycisk bez reakcji
   wygląda jak zawieszona strona — i ludzie klikają drugi raz, co wgrywa plik
   dwa razy. Blokujemy przycisk i mówimy, co się dzieje. */
document.addEventListener('submit', function (e) {
  var form = e.target;
  if (!form.querySelector('input[type=file]')) return;
  var btn = form.querySelector('button[type=submit], button:not([type])');
  if (btn) {
    btn.disabled = true;
    btn.textContent = 'Przetwarzam plik… to może potrwać kilkanaście sekund';
  }
});
