<?xml version="1.0" encoding="UTF-8"?>
<StyledLayerDescriptor version="1.0.0"
  xmlns="http://www.opengis.net/sld"
  xmlns:ogc="http://www.opengis.net/ogc"
  xmlns:xlink="http://www.w3.org/1999/xlink">
  <NamedLayer>
    <Name>fundiario_snci</Name>
    <UserStyle>
      <Title>SNCI - contorno leve por escala</Title>
      <Abstract>Contorno fino em escala estadual e detalhado no zoom; sem preenchimento para nao esconder as camadas ambientais.</Abstract>
      <FeatureTypeStyle>
        <!-- escala pequena (estado inteiro): só contorno muito fino, sem fill -->
        <Rule>
          <Name>contorno_estadual</Name>
          <MinScaleDenominator>1200000</MinScaleDenominator>
          <LineSymbolizer>
            <Stroke>
              <CssParameter name="stroke">#3B6E8A</CssParameter>
              <CssParameter name="stroke-width">0.25</CssParameter>
              <CssParameter name="stroke-opacity">0.7</CssParameter>
            </Stroke>
          </LineSymbolizer>
        </Rule>
        <!-- escala intermediária -->
        <Rule>
          <Name>contorno_intermediario</Name>
          <MinScaleDenominator>250000</MinScaleDenominator>
          <MaxScaleDenominator>1200000</MaxScaleDenominator>
          <LineSymbolizer>
            <Stroke>
              <CssParameter name="stroke">#3B6E8A</CssParameter>
              <CssParameter name="stroke-width">0.6</CssParameter>
            </Stroke>
          </LineSymbolizer>
        </Rule>
        <!-- zoom de imóvel: contorno forte + fill leve -->
        <Rule>
          <Name>contorno_detalhado</Name>
          <MaxScaleDenominator>250000</MaxScaleDenominator>
          <PolygonSymbolizer>
            <Fill>
              <CssParameter name="fill">#6B9FC8</CssParameter>
              <CssParameter name="fill-opacity">0.12</CssParameter>
            </Fill>
            <Stroke>
              <CssParameter name="stroke">#2E5C7A</CssParameter>
              <CssParameter name="stroke-width">1.0</CssParameter>
            </Stroke>
          </PolygonSymbolizer>
        </Rule>
      </FeatureTypeStyle>
    </UserStyle>
  </NamedLayer>
</StyledLayerDescriptor>
