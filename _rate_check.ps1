foreach ($pod in @('USCHI','USDAL','USDEN','USATL')) {
    foreach ($pol in @('HCM','HPH')) {
        try {
            $url = 'http://127.0.0.1:8100/api/rate-preview?pol=' + $pol + '&destinations=' + $pod + '&markup=20'
            $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 30
            $j = $r.Content | ConvertFrom-Json
            $found = $j.rates_found
            $total = $j.total_rates
            $count = $j.rates.Count
            $first = '-'
            if ($count -gt 0) {
                $first = $j.rates[0].carrier + ' $' + $j.rates[0].rate_40 + ' ' + $j.rates[0].rate_type
            }
            [string]::Format('{0}/{1} found={2} total={3} count={4} first={5}', $pol, $pod, $found, $total, $count, $first)
        } catch {
            [string]::Format('{0}/{1} ERR {2}', $pol, $pod, $_.Exception.Message)
        }
    }
}
